#!/usr/bin/python3

# -*- coding: utf-8 -*-
# create-upstream-tarballs - Utility to create the required source tarballs
#                            to package Thunderbird within Debian
# Copyright (c) 2022-2025 Carsten Schoenert <c.schoenert@t-online.de>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import logging
import os
import shutil
import sys
import tarfile
from zipfile import ZipFile

import requests
from lxml import html

try:
    from packaging.version import Version
except ImportError:
    print("pkg_resources library missing, please install python3-packaging!")
    sys.exit(1)

try:
    from tqdm.auto import tqdm
except ImportError:
    print("tqdm library missing, please install python3-tqdm!")
    sys.exit(1)

# local stuff
import repack

TB_BASE_URL_RELEASES = "https://download-origin.cdn.mozilla.net/pub/thunderbird/releases/"
TB_BASE_URL_CANDIDATES = "https://download-origin.cdn.mozilla.net/pub/thunderbird/candidates/"

try:
    import colorlog

    HAVE_COLORLOG = True
except ImportError:
    print(
        "colorlog library missing, no colored log possible, please install python3-colorlog if wanted!"
    )
    HAVE_COLORLOG = False


def create_logger():
    """
    Setup the logging environment.
    """
    log = logging.getLogger()  # root logger
    log.setLevel(logging.INFO)
    format_str = "%(asctime)s - [%(lineno)4d] %(levelname)-8s- %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    if HAVE_COLORLOG and os.isatty(2):
        cformat = "%(log_color)s" + format_str
        colors = {
            "DEBUG": "white",
            "INFO": "green",
            "WARNING": "bold_yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        }
        formatter = colorlog.ColoredFormatter(cformat, date_format, log_colors=colors)
    else:
        formatter = logging.Formatter(format_str, date_format)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)
    return logging.getLogger(__name__)


def option_parser():
    """
    Creates an argparser for various options.
    """
    parser = argparse.ArgumentParser(
        description="create-tarballs - collect all upstream data and creates "
        "thunderbird_$version.tar.orig{-l10n}.xz tarballs"
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable output of debug messages."
    )

    parser.add_argument(
        "-f",
        "--filter",
        action="store_true",
        help="Use dedicated file containing the elements to filter out.",
    )

    parser.add_argument(
        "-g",
        "--get-versions",
        action="store_true",
        help="Discover Mozilla CDN and returns the most "
        "recent available Thunderbird versions.",
    )

    parser.add_argument(
        "-r",
        "--repack",
        action="store_true",
        help="Strip out the unwanted and non needed files and create "
        "the thunderbird*.orig.tar.xz tarball, requires optional parameter -v.",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="store",
        help="Picks the data for the given version and creates the "
        "tarballs for later importing.",
    )

    return parser


def get_website_data(site):
    """
    Get the raw HTML data from 'site' and returns the HTML dom data.
    """
    try:
        page_data = requests.get(site, timeout=10)
    except requests.exceptions.ConnectionError as error:
        logging.error("Connection to Mozilla CDN not possible!")
        logging.debug("The following error did happen:\n%s", error)
        sys.exit(1)

    if page_data.status_code == requests.codes.ok:
        html_tree = html.fromstring(page_data.content)
        return html_tree
    else:
        return "None"


def get_latest_candidates_build(url):
    """
    Get the HTML data from the given URL and select all lines that are
    <a href=...> elements and split of the path from href.
    Finally count all found entries so we know the highest available build version.
    """
    logging.debug("Got URL %s", url)
    candidates_html = get_website_data(url)
    candidates_href_entries = candidates_html.xpath("//a /@href")
    latest_build = 0
    for elem in candidates_href_entries:
        line = elem.split("/")
        if len(line) == 7:
            if line[5].startswith("build"):
                build_count = int(line[5].strip("build"))
            if build_count > latest_build:
                latest_build = build_count
    logging.debug("Found folder 'build%s/' as most recent build.", latest_build)
    return latest_build


def check_for_version_transforming(version):
    """
    Transform a version string which contains a 'b' into a Debian conform
    string for beta versions.
    """
    if "b" in version:
        return "{0}~b{1}".format(version.split("b")[0], version.split("b")[1])
    else:
        return version


def get_versions():
    """
    Checks available Release and Beta versions on the Mozilla CDN site for
    Thunderbird.
    """

    # Step 1 - Get data about ESR candidates
    #
    # Crawling data containing the final candidates (ESR) versions. New
    # planned ESR versions will be first published and are visible here!
    tb_release_candidates_html = get_website_data(TB_BASE_URL_CANDIDATES)

    if tb_release_candidates_html != "None":
        tb_href_entries = tb_release_candidates_html.xpath("//a /@href")
        tb_upstream_candidates_non_versions = [] # List for all non ESR candidates versions.
        tb_upstream_candidates_esr_versions = [] # List for all ESR candidates versions.

        for elem in tb_href_entries:
            # Processing all href elements and collect all of them with a numeric version.
            line = elem.split("/")
            # Loop through all ESR versions.
            if (
                len(line) == 6
                and line[3] == "candidates"
                and "esr" in line[4]
            ):
                # We have now all versions with '-candidates' as suffix which
                # need to get split off and drop the 'esr' suffix.
                tb_upstream_candidates_esr_versions.append(line[4].split("-")[0].removesuffix("esr"))

            # Loop through all non ESR versions.
            elif (
                len(line) == 6
                and line[3] == "candidates"
                and "b" not in line[4]
            ):
                tb_upstream_candidates_non_versions.append(line[4].split("-")[0])

        tb_upstream_candidates_esr_versions.sort(key=lambda version: tuple(map(int, version.split('.'))))
        tb_upstream_candidates_non_versions.sort(key=lambda version: tuple(map(int, version.split('.'))))

        # Step 1.1 - Sorting the ESR candidates versions.
        #
        # Creating a list which is containing then again multiple lists of
        # major ESR versions.
        recent_major = 0
        tmp_major = 0
        tmp_esr_list = []

        for version in tb_upstream_candidates_esr_versions:
            recent_major = int(version.split(".")[0])

            if tmp_major < recent_major:
                tmp_major = recent_major
                tmp_esr_list.append([version])
            else:
                index = len(tmp_esr_list) - 1
                tmp_esr_list[index].extend([version])


    else:
        logging.error("Could not load versions from '%s'!", TB_BASE_URL_CANDIDATES)
        sys.exit(1)

    # Step 1.2 - Picking the recent ESR candidates versions.
    #
    # Getting the recent candidate version for the old (previous) ESR version.
    # Take the last element from the second last list.
    release_planned_old_esr_version = f"{tmp_esr_list[-2][-1]}esr"
    # And the build for this version.
    release_planned_old_esr_version_build = get_latest_candidates_build(
        f"{TB_BASE_URL_CANDIDATES}{release_planned_old_esr_version}-candidates/"
    )

    # Getting the recent candidate version for the new ESR version.
    # Take the last element from the last list.
    release_planned_next_esr_version = f"{tmp_esr_list[-1][-1]}esr"
    # And the build for this version.
    release_planned_next_esr_version_build = get_latest_candidates_build(
        f"{TB_BASE_URL_CANDIDATES}{release_planned_next_esr_version}-candidates/"
    )

    # Step 1.3 - Picking the most recent non ESR candidate version.
    #
    candidate_non_esr_version = tb_upstream_candidates_non_versions[-1]

    # Step 2 - Get data about released ESR and Beta versions
    #
    # Working on data containing the final released (ESR) versions. Found
    # versions here are really released as officially.
    tb_releases_html = get_website_data(TB_BASE_URL_RELEASES)

    if tb_releases_html != "None":
        tb_href_entries = tb_releases_html.xpath("//a /@href")
        # Variable to include all released ESR versions.
        tb_upstream_release_versions = []
        for elem in tb_href_entries:
            # Processing all href elements and collect all of them with a numeric version.
            line = elem.split("/")
            if len(line) == 6:
                # Exclude all non numeric elements. But also all versions
                # which never will become a ESR version.
                if line[4] not in [
                    "custom-updates",
                    "latest",
                    "latest-beta",
                ]:
                    tb_upstream_release_versions.append(line[4])

    else:
        logging.error("Could not load versions from '%s'!", TB_BASE_URL_RELEASES)
        sys.exit(1)

    # Step 3 - Find most recent Release and Beta versions.
    #
    # Step 3.1 - Create (three) lists for each version type.
    #
    # One for ESR Releases "*esr", one for Release "beta" versions and one
    # for the non ESR versions.
    esr_release_versions = []
    beta_release_versions = []
    release_non_esr_versions = []
    for version in tb_upstream_release_versions:
        if "esr" in str(version):
            esr_release_versions.append(version.removesuffix("esr"))

        elif "b" in str(version):
            beta_release_versions.append(version)

        elif (
            "rc" not in str(version) and
            "a" not in str(version) and
            "real" not in str(version)
        ):
            release_non_esr_versions.append(version)

    # Step 3.2 - Sort the Release "*esr" list and the non ESR releases by
    # numeric numbers ascending.
    #
    esr_release_versions.sort(key=lambda version: tuple(map(int, version.split('.'))))
    release_non_esr_versions.sort(key=lambda version: tuple(map(int, version.split('.'))))

    # Step 3.3 - Get the most previous and current Release ESR versions.
    #
    recent_major = 0
    tmp_major = 0
    tmp_release_list = []

    for version in esr_release_versions:
        recent_major = int(version.split(".")[0])

        if tmp_major < recent_major:
            tmp_major = recent_major
            tmp_release_list.append([version])
        else:
            index = len(tmp_release_list) - 1
            tmp_release_list[index].extend([version])

    # Picking the recent version for the old (previous) ESR version.
    # Take the last element from the second last list.
    release_prev_esr_version = f"{tmp_release_list[-2][-1]}esr"

    # Picking the recent version for the new ESR version.
    # Take the last element from the last list.
    release_cur_esr_version = f"{tmp_release_list[-1][-1]}esr"

    # Step 3.4 - Get the newest "beta" version.
    #
    beta_version = tb_upstream_release_versions[1]
    for pos in range(2, len(beta_release_versions)):
        if "b" in beta_release_versions[pos]:
            check = Version(beta_version) < Version(
                beta_release_versions[pos]
            )
            if check:
                beta_version = beta_release_versions[pos]

    # Step 4 - Find the most recent non ESR versions.
    #
    release_non_esr_version = release_non_esr_versions[-1]

    logging.debug(
        "Current Release ESR (previous) version: %s",
        release_prev_esr_version
    )
    logging.debug(
        "Current Release ESR (current) version: %s",
        release_cur_esr_version
    )
    logging.debug(
        "Current Release non ESR version: %s",
        release_non_esr_version
    )
    logging.debug(
        "Current Candidate ESR (previous) version: %s (build%s)",
        release_planned_old_esr_version,
        release_planned_old_esr_version_build
    )
    logging.debug(
        "Current Candidate ESR (current) version: %s (build%s)",
        release_planned_next_esr_version,
        release_planned_next_esr_version_build
    )
    logging.debug(
        "Current Candidate non ESR version: %s",
        candidate_non_esr_version
    )
    logging.debug("Current Beta version: %s", beta_version)

    return [
        release_prev_esr_version,
        release_cur_esr_version,
        release_planned_old_esr_version,
        release_planned_old_esr_version_build,
        release_planned_next_esr_version,
        release_planned_next_esr_version_build,
        beta_version,
        release_non_esr_version,
        candidate_non_esr_version,
    ]


def get_xpi_languages(base_url):
    """
    Picks up the available XPI languages from a given URL.
    """
    logging.debug("Using %s to search for xpi files.", base_url)
    xpi_html = get_website_data(base_url)

    # Try to get xpath data elements, will be successful if the URL is a
    # valid and usable URL for the requested version! Version to download
    # which are set manually will always be looked for on the release channel.
    try:
        xpi_href_entries = xpi_html.xpath("//a /@href")
    except AttributeError:
        logging.error("Requested version not found on '%s'!", base_url)
        logging.error("Is the version really available on the release channel?")
        sys.exit(1)
    xpi_list = []
    for elem in xpi_href_entries:
        line = elem.split("/")
        # We'll have a list like this:
        # ['', 'pub', 'thunderbird', 'candidates', '$(version)-candidates', 'build1', 'linux-x86_64', 'xpi', '$(lang).xpi']
        # We can ignore the en-US language, as this is the native language of TB.

        # Catch up XPI data from release channel.
        if len(line) == 8 and line[3] == "releases":
            if not line[7].endswith("en-US.xpi"):
                xpi_list.append(line[7])

        # Catch up XPI data from candidates channel.
        if len(line) == 9 and line[3] == "candidates":
            if not line[8].endswith("en-US.xpi"):
                xpi_list.append(line[8])

    if len(xpi_list) > 0:
        logging.info("Found %d xpi files on remote side.", len(xpi_list))
        return xpi_list
    else:
        logging.error("Something went wrong while collecting XPI languages!")
        sys.exit(1)


def select_upstream_version(detected_upstream_versions):
    """
    Gives back the upstream version the user wants to proceed.
    """
    while True:
        print("\nPlease select the Thunderbird version to download!")
        print("------------------------------------------")
        print(f"1 - Current ESR Release (previous) version: {detected_upstream_versions[0]}")
        print(f"2 - Current ESR Release (current) version:  {detected_upstream_versions[1]}")
        print("------------------------------------------")
        print(f"3 - Current Planned ESR (previous) version: {detected_upstream_versions[2]} build{detected_upstream_versions[3]}")
        print(f"4 - Current Planned ESR (current) version:  {detected_upstream_versions[4]} build{detected_upstream_versions[5]}")
        print("------------------------------------------")
        print(f"5 - Current Beta version:                   {detected_upstream_versions[6]}")
        print(f"6 - Current non ESR Release version:        {detected_upstream_versions[7]}")
        print(f"7 - Current non ESR Candidate version:      {detected_upstream_versions[8]}")
        print("------------------------------------------")
        print("8 - Do nothing and Exit\n")
        print("Your selection: ", end=" ")
        try:
            version = int(input())
            if version not in range(1, 9):
                print("\u001b[31mWrong input!\u001b[0m Please select a valid number for choosing.")
            elif version == 8:
                logging.info("Action aborted by the user.")
                sys.exit(1)
            else:
                print()
                break
        except ValueError:
            print("\u001b[31mWrong input!\u001b[0m Please select a valid number for choosing.")
        except KeyboardInterrupt:
            print("   \u001b[31mAborted!\u001b[0m")
            sys.exit(1)

    if version == 1:
        return detected_upstream_versions[0]
    elif version == 2:
        return detected_upstream_versions[1]
    elif version == 3:
        return [detected_upstream_versions[2], detected_upstream_versions[3]]
    elif version == 4:
        return [detected_upstream_versions[4], detected_upstream_versions[5]]
    elif version == 5:
        return detected_upstream_versions[6]
    elif version == 6:
        return detected_upstream_versions[7]
    elif version == 7:
        return detected_upstream_versions[8]


def download_file(url, file, target_folder):
    """
    Download a given file.
    If file is already locally available check if a new download is required.
    """
    with requests.get(url, stream=True, timeout=10) as r:
        # Check header to get content length in bytes.
        total_length = int(r.headers.get("Content-Length"))
        if os.path.isfile(f"{target_folder}/{file}"):
            file_size = os.path.getsize(f"{target_folder}/{file}")
            if total_length != file_size:
                logging.warning(
                    "Found file '%s' locally, but existing file size differs! Removing!", file
                )
                os.unlink(f"{target_folder}/{file}")
            else:
                logging.debug(
                    "Found file '%s' locally and file size matches upstream size, skipping download.", file
                )
                return

        logging.info("Download %s", url)
        with tqdm.wrapattr(
            r.raw, "read", total=total_length, ncols=100, desc="{:9s}".format(file)
        ) as raw:
            with open(f"{target_folder}/{file}", "wb") as output:
                shutil.copyfileobj(raw, output)


def collect_tb_upstream_data(tb_version):
    """
    Collect all required upstream files needed to create and recreate the
    tarballs locally.
    """

    if not isinstance(tb_version, list):
        file = f"thunderbird-{tb_version}.source.tar.xz"
        # Concatenate URLs for ESR or Beta version.
        if "b" not in tb_version:
            tb_url = f"{TB_BASE_URL_RELEASES}{tb_version}/source/{file}"
            xpi_url = f"{TB_BASE_URL_RELEASES}{tb_version}/linux-x86_64/xpi"
        else:
            build_nb = get_latest_candidates_build(
                f"{TB_BASE_URL_CANDIDATES}{tb_version}-candidates/"
            )
            tb_url = f"{TB_BASE_URL_CANDIDATES}{tb_version}-candidates/build{build_nb}/source/{file}"
            xpi_url = f"{TB_BASE_URL_CANDIDATES}{tb_version}-candidates/build{build_nb}/linux-x86_64/xpi"
    else:
        file = f"thunderbird-{tb_version[0]}.source.tar.xz"
        # Concatenate URLs for planned ESR version.
        tb_url = f"{TB_BASE_URL_CANDIDATES}{tb_version[0]}-candidates/build{tb_version[1]}/source/{file}"
        xpi_url = f"{TB_BASE_URL_CANDIDATES}{tb_version[0]}-candidates/build{tb_version[1]}/linux-x86_64/xpi"

    xpi_languages = get_xpi_languages(f"{xpi_url}/")

    if not os.path.isdir(download_folder):
        logging.info("Create folder %s", download_folder)
        os.mkdir(download_folder)

    # Getting Thunderbird sources.
    download_file(tb_url, file, download_folder)

    # Getting the language XPI files.
    for xpi_file in xpi_languages:
        download_file(f"{xpi_url}/{xpi_file}", xpi_file, download_folder)
    return xpi_languages


def create_tb_l10n_tarball(xpi_languages, base_folder, upstream_version):
    """
    Create the additional thunderbird_$version.orig-l10n.tar.xz component
    tarball.
    """
    logging.info("Prepare data for l10n component tarball.")
    l10n_upstream_folder = f"{base_folder}/thunderbird-l10n"

    if os.path.isdir(l10n_upstream_folder):
        if len([entry for entry in os.listdir(l10n_upstream_folder)]) > 0:
            for entry in os.scandir(l10n_upstream_folder):
                if entry.is_dir(follow_symlinks=False) or entry.is_file():
                    if entry.is_dir():
                        logging.debug(
                            "Removing folder %s/%s", l10n_upstream_folder, entry.name
                        )
                        shutil.rmtree(f"{l10n_upstream_folder}/{entry.name}")
                    if entry.is_file():
                        logging.debug(
                            "Removing file %s/%s", l10n_upstream_folder, entry.name
                        )
                        os.unlink(f"{l10n_upstream_folder}/{entry.name}")
        else:
            logging.debug("'%s' exists, but nothing to clean up.", l10n_upstream_folder)

    else:
        logging.debug(
            "Create folder '%s' for xpi l10n upstream data.", l10n_upstream_folder
        )
        os.mkdir(l10n_upstream_folder)

    logging.info("Extract l10n data.")
    for xpi in xpi_languages:
        l10n_folder = f"{l10n_upstream_folder}/" + xpi.split(".")[0]
        l10n_xpi_file = f"{base_folder}/{xpi}"
        logging.debug("Create folder %s", l10n_folder)
        os.mkdir(l10n_folder)
        logging.debug("Extract data from %s", l10n_xpi_file)
        with ZipFile(l10n_xpi_file, "r") as zipfile:
            zipfile.extractall(l10n_folder)

    if not isinstance(upstream_version, list):
        # Version number for Beta and ESR versions.
        version = check_for_version_transforming(upstream_version)
    else:
        # Version number for planned ESR version.
        version = f"{upstream_version[0]}"

    l10n_component_name = f"thunderbird_{version}.orig-thunderbird-l10n.tar.xz"
    logging.info("Build l10n component tarball %s", l10n_component_name)

    # Build the component tarball with the l10n data.
    with tarfile.open(f"{download_folder}/../{l10n_component_name}", "w:xz") as tar:
        tar.add(l10n_upstream_folder, arcname=os.path.basename(l10n_upstream_folder))

    return l10n_component_name


def compare_xpi_languages(l10n_languages_remote):
    """
    Doings some simple sanity checks to see if a new languages is provided by upstream.
    """
    # Get listing of the folder thunderbird-l10n.
    l10n_languages_local = os.listdir(
        f"{os.path.dirname(os.path.abspath(__file__))}/../thunderbird-l10n"
    )
    l10n_languages_local_control = []

    # Get a list l10n packages from debian/control.
    with open(os.path.join(os.path.dirname(__file__), "control"), encoding="utf-8") as control:
        lines = control.readlines()
        for line in lines:
            if line.startswith("Package: thunderbird-l10n-") and "-all" not in line:
                l10n_languages_local_control.append(
                    line.replace("\n", "").split("Package: thunderbird-l10n-")[1:][0]
                )

    for lang in l10n_languages_remote:
        l10n_language_remote = lang.split(".")[0]

        if l10n_language_remote not in l10n_languages_local:
            logging.warning(
                "Found language '%s' within upstream data, but not in folder thunderbird-l10n/ !", l10n_language_remote
            )

        if l10n_language_remote.lower() not in l10n_languages_local_control:
            logging.warning(
                "Found language '%s' within upstream data, but not in debian/control !", l10n_language_remote
            )


def do_repack(source, target, filter_elements):
    """
    Takes the source tarball and filter out all the given elements into the
    target tarball.
    """
    logging.debug("Create %s from %s using %s.", target, source, filter_elements)
    repack.filter_tar(source, target, filter_elements)


if __name__ == "__main__":
    create_logger()
    logging.info("%s started", os.path.basename(sys.argv[0]))

    # The base path the tarballs will get placed finally.
    tarball_path = os.path.dirname(os.path.abspath("./"))

    args = option_parser().parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    logging.debug("Using args: %s", args)

    if not args.filter:
        args.filter = os.path.join(os.path.dirname(__file__), "source.filter")

    if args.repack:
        if args.get_versions:
            logging.error("Option --get-versions can't be used together with --repack!")
            option_parser().print_help()
            sys.exit(1)
        if not args.version:
            logging.error("Option --repack requires parameter --version!")
            sys.exit(1)
        else:
            version = args.version
        source = f"{tarball_path}/thunderbird-{version}.source.tar.xz"
        target = f"{tarball_path}/thunderbird_{version}.orig.tar.xz"
        do_repack(source, target, args.filter)

    if args.get_versions:
        upstream_versions = get_versions()
        logging.info(
            "Current most recent TB Release ESR (previous) version:   %s",
            upstream_versions[0]
        )
        logging.info(
            "Current most recent TB Release ESR (current) version:    %s",
            upstream_versions[1]
        )
        logging.info(
            "Current most recent TB Candidate ESR (previous) version: %s build%s",
            upstream_versions[2],
            upstream_versions[3]
        )
        logging.info(
            "Current most recent TB Candidate ESR (current) version:  %s build%s",
            upstream_versions[4],
            upstream_versions[5]
        )
        logging.info(
            "Current most recent TB Beta version:                     %s",
            upstream_versions[6]
        )
        logging.info(
            "Current most recent non ESR Release:                     %s",
            upstream_versions[7]
        )
        logging.info(
            "Current most recent non ESR Candidate:                   %s",
            upstream_versions[7]
        )
        sys.exit(0)

    if args.version:
        target_version = args.version
        version = args.version
    else:
        target_version = select_upstream_version(get_versions())
        if not isinstance(target_version, list):
            version = check_for_version_transforming(target_version)
        else:
            version = target_version[0]

    download_folder = f"../tb-preparation-{version}"
    logging.debug("Upstream version to get: %s", version)

    # Download Thunderbird source tarball and also the upstream data of l10n
    # languages Add-ons.
    l10n_languages = collect_tb_upstream_data(target_version)

    # Build the additional Debian packaging component tarball.
    tb_l10n_component_name = create_tb_l10n_tarball(
        l10n_languages, download_folder, target_version
    )

    if not isinstance(target_version, list):
        version = check_for_version_transforming(target_version)
        # Catching potential upstream Beta versions without any version
        # string manipulation we need to do for Debian.
        source = f"{download_folder}/thunderbird-{target_version}.source.tar.xz"
    else:
        version = target_version[0]
        source = f"{download_folder}/thunderbird-{version}.source.tar.xz"

    target = f"{tarball_path}/thunderbird_{version}.orig.tar.xz"
    logging.info("Build source tarball thunderbird_%s.orig.tar.xz", version)
    do_repack(source, target, args.filter)

    logging.info(
        "Thunderbird source tarball prepared as:         %s/thunderbird_%s.orig.tar.xz",
        tarball_path, version
    )
    logging.info(
        "Thunderbird l10n component tarball prepared as: %s/%s",
        tarball_path,
        tb_l10n_component_name
    )

    # Some checking if further adjustments are required to have packaging in
    # sync to provided l10n data by upstream.
    compare_xpi_languages(l10n_languages)

# vim:tw=0:
