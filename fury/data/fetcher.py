"""Fetcher based on dipy."""

import os
import sys
import contextlib

from os.path import join as pjoin
from hashlib import sha256
from shutil import copyfileobj

import tarfile
import zipfile

if sys.version_info[0] < 3:
    from urllib2 import urlopen
else:
    from urllib.request import urlopen

# Set a user-writeable file-system location to put files:
if 'FURY_HOME' in os.environ:
    fury_home = os.environ['FURY_HOME']
else:
    fury_home = pjoin(os.path.expanduser('~'), '.fury')

# The URL to the University of Washington Researchworks repository:
UW_RW_URL = \
    "https://digital.lib.washington.edu/researchworks/bitstream/handle/"

FURY_DATA_URL = \
    "https://raw.githubusercontent.com/fury-gl/fury-data/master/examples/"

MODEL_DATA_URL = \
    "https://raw.githubusercontent.com/fury-gl/fury-data/master/models/"


class FetcherError(Exception):
    pass


def update_progressbar(progress, total_length):
    """Show progressbar.

    Takes a number between 0 and 1 to indicate progress from 0 to 100%.
    """
    # Try to set the bar_length according to the console size
    try:
        columns = os.popen('tput cols', 'r').read()
        bar_length = int(columns) - 46
        if bar_length < 1:
            bar_length = 20
    except Exception:
        # Default value if determination of console size fails
        bar_length = 20
    block = int(round(bar_length * progress))
    size_string = "{0:.2f} MB".format(float(total_length) / (1024 * 1024))
    text = "\rDownload Progress: [{0}] {1:.2f}%  of {2}".format(
        "#" * block + "-" * (bar_length - block), progress * 100, size_string)
    sys.stdout.write(text)
    sys.stdout.flush()


def copyfileobj_withprogress(fsrc, fdst, total_length, length=16 * 1024):
    copied = 0
    while True:
        buf = fsrc.read(length)
        if not buf:
            break
        fdst.write(buf)
        copied += len(buf)
        progress = float(copied) / float(total_length)
        update_progressbar(progress, total_length)


def _already_there_msg(folder):
    """Print a message indicating that dataset is already in place."""
    msg = 'Dataset is already in place. If you want to fetch it again '
    msg += 'please first remove the folder %s ' % folder
    print(msg)


def _get_file_sha(filename):
    """Generates SHA checksum for the entire file in blocks of 256

    Parameters
    ----------
    filename: str
        The path to the file whose sha checksum is to be generated

    Returns
    -------
    sha256_data: str
        The computed sha hash from the input file

    """
    sha256_data = sha256()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(256*sha256_data.block_size), b''):
            sha256_data.update(chunk)
    return sha256_data.hexdigest()


def check_sha(filename, stored_sha256=None):
    """Checks the generated sha checksum.

    Parameters
    ----------
    filename: str
        The path to the file whose checksum is to be compared
    stored_sha256: str, optional
        Used to verify the generated SHA checksum.
        Default: None, checking is skipped

    """
    if stored_sha256 is not None:
        computed_sha256 = _get_file_sha(filename)
        if stored_sha256.lower() != computed_sha256:
            msg = """The downloaded file, %s,
             does not have the expected sha
            checksum of "%s".
             Instead, the sha checksum was: "%s".
             This could mean that
            something is wrong with the file
             or that the upstream file has been updated.
            You can try downloading the file again
             or updating to the newest version of
            Fury.""" % (filename, stored_sha256, computed_sha256)
            raise FetcherError(msg)


def _get_file_data(fname, url):
    with contextlib.closing(urlopen(url)) as opener:
        try:
            response_size = opener.headers['content-length']
        except KeyError:
            response_size = None

        with open(fname, 'wb') as data:
            if response_size is None:
                copyfileobj(opener, data)
            else:
                copyfileobj_withprogress(opener, data, response_size)


def fetch_data(files, folder, data_size=None):
    """Downloads files to folder and checks their sha checksums.

    Parameters
    ----------
    files : dictionary
        For each file in `files` the value should be (url, sha). The file will
        be downloaded from url if the file does not already exist or if the
        file exists but the sha checksum does not match.
    folder : str
        The directory where to save the file, the directory will be created if
        it does not already exist.
    data_size : str, optional
        A string describing the size of the data (e.g. "91 MB") to be logged to
        the screen. Default does not produce any information about data size.

    Raises
    ------
    FetcherError
        Raises if the sha checksum of the file does not match the expected
        value. The downloaded file is not deleted when this error is raised.

    """
    if not os.path.exists(folder):
        print("Creating new folder %s" % (folder))
        os.makedirs(folder)

    if data_size is not None:
        print('Data size is approximately %s' % data_size)

    all_skip = True
    for f in files:
        url, sha = files[f]
        fullpath = pjoin(folder, f)
        if os.path.exists(fullpath) and (_get_file_sha(fullpath) == sha.lower()):
            continue
        all_skip = False
        print('Downloading "%s" to %s' % (f, folder))
        _get_file_data(fullpath, url)
        check_sha(fullpath, sha)
    if all_skip:
        _already_there_msg(folder)
    else:
        print("Files successfully downloaded to %s" % (folder))


def _make_fetcher(name, folder, baseurl, remote_fnames, local_fnames,
                  sha_list=None, doc="", data_size=None, msg=None,
                  unzip=False):
    """Create a new fetcher.

    Parameters
    ----------
    name : str
        The name of the fetcher function.
    folder : str
        The full path to the folder in which the files would be placed locally.
        Typically, this is something like 'pjoin(fury_home, 'foo')'
    baseurl : str
        The URL from which this fetcher reads files
    remote_fnames : list of strings
        The names of the files in the baseurl location
    local_fnames : list of strings
        The names of the files to be saved on the local filesystem
    sha_list : list of strings, optional
        The sha checksums of the files. Used to verify the content of the
        files. Default: None, skipping checking sha.
    doc : str, optional.
        Documentation of the fetcher.
    data_size : str, optional.
        If provided, is sent as a message to the user before downloading
        starts.
    msg : str, optional.
        A message to print to screen when fetching takes place. Default (None)
        is to print nothing
    unzip : bool, optional
        Whether to unzip the file(s) after downloading them. Supports zip, gz,
        and tar.gz files.

    Returns
    -------
    fetcher : function
        A function that, when called, fetches data according to the designated
        inputs

    """
    def fetcher():
        files = {}
        for i, (f, n), in enumerate(zip(remote_fnames, local_fnames)):
            files[n] = (baseurl + f, sha_list[i] if
                        sha_list is not None else None)
        fetch_data(files, folder, data_size)

        if msg is not None:
            print(msg)
        if unzip:
            for f in local_fnames:
                split_ext = os.path.splitext(f)
                if split_ext[-1] == '.gz' or split_ext[-1] == '.bz2':
                    if os.path.splitext(split_ext[0])[-1] == '.tar':
                        ar = tarfile.open(pjoin(folder, f))
                        ar.extractall(path=folder)
                        ar.close()
                    else:
                        raise ValueError('File extension is not recognized')
                elif split_ext[-1] == '.zip':
                    z = zipfile.ZipFile(pjoin(folder, f), 'r')
                    z.extractall(folder)
                    z.close()
                else:
                    raise ValueError('File extension is not recognized')

        return files, folder

    fetcher.__name__ = name
    fetcher.__doc__ = doc
    return fetcher


fetch_viz_icons = _make_fetcher("fetch_viz_icons",
                                pjoin(fury_home, "icons"),
                                UW_RW_URL + "1773/38478/",
                                ['icomoon.tar.gz'],
                                ['icomoon.tar.gz'],
                                ['BC1FEEA6F58BA3601D6A0B029EB8DFC5F352E21F2A16BA41099A96AA3F5A4735'],
                                data_size="12KB",
                                doc="Download icons for fury",
                                unzip=True
                                )


fetch_viz_wiki_nw = _make_fetcher("fetch_viz_wiki_nw",
                                  pjoin(fury_home, "examples", "wiki_nw"),
                                  FURY_DATA_URL,
                                  ['wiki_categories.txt', 'wiki_edges.txt',
                                   'wiki_positions.txt'],
                                  ['wiki_categories.txt', 'wiki_edges.txt',
                                   'wiki_positions.txt'],
                                  ['1679241B13D2FD01209160F0C186E14AB55855478300B713D5369C12854CFF82',
                                   '702EE8713994243C8619A29C9ECE32F95305737F583B747C307500F3EC4A6B56',
                                   '044917A8FBD0EB980D93B6C406A577BEA416FA934E897C26C87E91C218EF4432'],
                                  doc="Download the following wiki information"
                                      "Interdisciplinary map of the journals",
                                  msg=("More information about complex "
                                       "networks can be found in this papers:"
                                       " https://arxiv.org/abs/0711.3199")
                                  )

fetch_viz_models = _make_fetcher("fetch_viz_models",
                                 pjoin(fury_home, "models"),
                                 MODEL_DATA_URL,
                                 ['utah.obj'],
                                 ['utah.obj'],
                                 ['0B50F12CEDCDC27377AC702B1EE331223BECEC59593B3F00A9E06B57A9C1B7C3'],
                                 doc="Download the model for shader tutorial"
                                 )


def read_viz_icons(style='icomoon', fname='infinity.png'):
    """Read specific icon from specific style.

    Parameters
    ----------
    style : str
        Current icon style. Default is icomoon.
    fname : str
        Filename of icon. This should be found in folder HOME/.fury/style/.
        Default is infinity.png.

    Returns
    --------
    path : str
        Complete path of icon.

    """
    folder = pjoin(fury_home, 'icons', style)
    return pjoin(folder, fname)


def read_viz_models(fname):
    """Read specific model.

    Parameters
    ----------
    fname : str
        Filename of the model.
        This should be found in folder HOME/.fury/models/.

    Returns
    --------
    path : str
        Complete path of models.

    """
    folder = pjoin(fury_home, 'models')
    return pjoin(folder, fname)
