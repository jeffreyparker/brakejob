"""
BrakeJob will scan the specified folder for all subfolders containing DVD
images. Each DVD will be scanned for titles, and the passed-in encoding settings
will be applied to all of them.

Besides the standard HandBrake settings, BrakeJob also supports specifying
subtitle encoding. For example, you can specify that every encoding have any
foreign language subtitles burned into the video, and the English subtitles
to be toggleable on/off (when using the MKV container)

Example Usage:

* View a list of titles to be encoded from a directory and the resulting HandBrakeCLI
calls that it will make:
python brakejob.py --source-dir "C:\Users\Jeff\Documents\DVDFab\FullDisc"

* Encode a directory just using the 'Normal' HandBrake preset:
python brakejob.py --source-dir "C:\Users\Jeff\Documents\DVDFab\FullDisc" --handbrake-args "-Z Normal" --encode

* Encode a directory using the Normal preset, but also add detelecine and decomb, using mkv container,
burn-in any foreign subs and include the English langauge soft-subs (toggleable on/off)
python brakejob.py --source-dir "C:\Users\Jeff\Documents\DVDFab\FullDisc" --native-lang eng --burn-foreign-subs --sub-langs eng --extension mkv --handbrake-args "-Z Normal -f mkv --detelecine --decomb" --encode
"""
# Copyright 2010, Jeffrey Parker (jeffreyparker@gmail.com)
#
# GPLv2 License:
# --------------
# Copyright (C) 2010, Jeffrey Parker (jeffreyparker@gmail.com)
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more 
# details.
#
# You should have received a copy of the GNU General Public License along with 
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA 02111-1307 USA
#
# You can also read the license at:
#
#  http://www.opensource.org/licenses/gpl-2.0.php

import copy
import logging
import operator
import optparse
import os
import platform
from pprint import pprint, pformat
import shlex
import subprocess
import sys
import traceback

from pyparsing import alphas,nums, dblQuotedString, Combine, Word, Group, Dict, delimitedList, Suppress, removeQuotes, Literal, restOfLine, ZeroOrMore, SkipTo, ParserElement

logger = logging.getLogger("logger")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
logger.addHandler(ch)

VALID_FILES = ['.iso']
VALID_FOLDER_FILES = ['.ifo','.vob']
DEFAULT_THRESHOLD = 0.10
DEFAULT_LANG = 'eng'
DEFAULT_HB = os.path.join(os.getcwd(),'HandBrakeCLI.exe')
DEFAULT_VERBOSITY = '0'
DEFAULT_FORMAT = 'mp4'
VERSION = '0.1.2'
USAGE = "%prog --source-dir <dir> [--handbrake-args <\"args\">] [--encode] [other options]"

# Just raw interaction with the HandBrake CLI goes here, no actual decisions
# or 'smarts'
class Handbrake():
    
    hb_path = None
    
    def __init__(self, hb_path):
        self.hb_path = hb_path
        
    def call(self, dict_options = None, raw_options = None, ignore_output = True):
        args = []
        if (raw_options):
            args += raw_options
        if (dict_options):
            args += self._convert_dict_to_args(dict_options)
        call = [self.hb_path] + args
        if ignore_output:
            # Output will just goto console, nice during rendering so user sees the progress
            logger.debug("ENCODING: " + str(call))
            p = subprocess.Popen(call)
        else:
            # Capture the output so we can parse it
            logger.debug("CALLING: " + str(call))
            p = subprocess.Popen(call, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        output = p.communicate()[0]
        return output
    
    def _convert_dict_to_args(self, options):
        args = []
        for option in options.keys():
            args.append("--"+str(option))
            args.append(str(options[option]))
        return args
        
    def sim(self, dict_options = None, raw_options = None, ignore_output = True):
        args = []
        if (raw_options):
            args += raw_options
        if (dict_options):
            args += self._convert_dict_to_args(dict_options)
        call = [self.hb_path] + args
        logger.info(' '.join(call))
        
    # Returns duration and subtitle info about each title on the DVD
    def get_disc_info(self, input_file):
        title_options = {'title':0, 'input':input_file}
        output = self.call(dict_options = title_options, ignore_output = False)
        tokens = self._get_handbrake_title_pattern().scanString(output)
        titles = []
        for (token,start,end) in tokens:
            seconds = self._convert_duration_to_seconds(token.duration)
            subtitles = {}
            # Subtitle data is an array of (#,lang) array pairs. Not ideal but it's
            # the best I can figure out how to get out of pyparsing
            for subdata in token.subtitles:
                subtitles[subdata[0]] = subdata[1]
            title = {'title':token.title, 'duration':seconds, 'subtitles':subtitles}
            titles.append(title)
        disc = None
        if len(titles) > 0:
            disc = DiscInfo(path = input_file, titles = titles)
        return disc

    # Always returns constant pattern
    def _get_handbrake_title_pattern(self):
        title = Literal("+ title").suppress()
        integer = Word("0123456789")
        time = Combine(integer + ":" + integer + ":" + integer)
        duration = Literal("+ duration:").suppress()
        subtitle = Literal("+ subtitle tracks:")
        iso = Literal('(iso639-2:').suppress() + Word(alphas)
        subtitle_track = Literal("+").suppress() + Group(integer + SkipTo(iso).suppress() + iso) + restOfLine.suppress()

        title_num = integer.setResultsName("title")
        duration_num = time.setResultsName("duration")
        subtitles = Group(ZeroOrMore(subtitle_track)).setResultsName("subtitles")

        pattern = title + title_num + \
            SkipTo(duration).suppress() + \
            duration + duration_num + \
            SkipTo(subtitle).suppress() + subtitle.suppress() + subtitles
            
        return pattern
        
    def _convert_duration_to_seconds(self, duration):
        (hours,minutes,seconds) = duration.split(':')
        seconds = (int(hours) * 3600) + (int(minutes) * 60) + int(seconds)
        return seconds
     
    def encode_disc(self, settings):
        self.call(dict_options = settings)


class DiscInfo():

    path = None
    titles = None
    name = None

    def __init__(self, path, titles):
        if not path:
            raise Exception('Trying to create disc with invalid path')
        if len(titles) is 0:
            raise Exception('Trying to create disc with 0 titles')
        self.path = path
        self.titles = titles
        (root, ext) = os.path.splitext(path)
        self.name = os.path.basename(root)
    
    def is_tv_show(self):
        # TODO Analyze show and make guess
        return True
        
    def __repr__(self):
        return self.path + '\n' + pformat(self.titles)
        
    def filter(self, filter):
        self.titles = filter.filter(self.titles)
        
    def remove_titles(self, titles):
        # Remove the passed-in titles from the DiscInfo titles.
        self.titles[:] = [t for t in self.titles if t.get('title') not in titles]


class TvFilter():

    threshold = None

    def __init__(self, threshold = 0.10):
        self.threshold = threshold
    
    # Only encode the titles we think are episodes
    def filter(self, titles):
        if len(titles) < 2:
            # Maybe this actually is a tv disc with only one episode,
            # but better for the user to manually check it out
            raise Exception("This doesn't look like a TV show disc")

        # Most TV show DVDs have ~4 episodes between ~25min - 1hr, and a few short
        # (<5min) titles like DVD menus, special features, etc. Sometimes they also
        # have one title that is all of the episodes on the disc combined into one.
        #
        # The current technique to find only the correct episodes is to use the 2nd
        # longest title as a baseline (in case there's the 'combined' episode), and
        # assume that any title within a certain percent length of it is a
        # valid episode
        #
        # This currently does NOT take into account the occasional double-length
        # episode.
        
        titles.sort(key=operator.itemgetter('duration'))
        base_length = int(titles[-2]['duration']) # Length of 2nd longest title
        threshold = int(self.threshold * int(base_length))
        min_length = base_length - threshold
        max_length = base_length + threshold
        
        filtered = []
        
        logger.debug("(Baseline duration is %s sec)" %base_length)
        
        for title in titles:
            if title['duration'] >= min_length and title['duration'] <= max_length:
                filtered.append(title)
            else:
                logger.debug("Skipping title %s because it doesn't appear to be the right length: %s sec" %(title['title'], title['duration']))
                

        # Put back in title order because that seems more natural
        filtered.sort(key=operator.itemgetter('title'))
        return filtered
 
class MovieFilter():

    #TODO
    def filter(self, titles):
        return titles


def duplicate_filter(disc):
    titles = disc.titles

    filtered = []
    added_list = []
    for title in titles:
        if title['duration'] not in added_list:
            #filtered.append(title)
            added_list.append(title['duration'])
        else:
            filtered.append(title['title'])
            #logger.debug("Skipping title %s because it looks like a duplicate. Please manually verify!" %title['title'])
    return filtered

def encode_disc_with_settings(disc, handbrake, encode_settings):

    if encode_settings['tv_detection']:
        disc.filter(TvFilter(threshold = encode_settings['threshold']))

    filtered_titles = duplicate_filter(disc)
    if len(filtered_titles) > 0:
        if encode_settings['duplicate_detection']:
            disc.remove_titles(filtered_titles)
            logger.info("Skipping the following titles because they look like duplicates. Please manually verify!")
        else:
            logger.info("Potential duplicate titles found. Add --duplicate_detection to filter the following out:")
        for title in filtered_titles:
            logger.info("Title "+title)
        logger.info("")

    for title in disc.titles:
        handbrake_args = calc_handbrake_args(disc, title, encode_settings)
        if os.path.isfile(handbrake_args['output']):
            logger.warning("Skipping encode because %s already exists!" %handbrake_args['output'])

        if encode_settings['simulate']:
            handbrake.sim(dict_options = handbrake_args, raw_options = encode_settings['passthrough_args'])
        else:
            handbrake.call(dict_options = handbrake_args, raw_options = encode_settings['passthrough_args'])

def calc_handbrake_args(disc, title, settings):
        # Name e.g.: c:\path\2.mkv
        output_filename = os.path.join(settings['output_dir'],(disc.name + ' - ' + title['title'] + '.' + settings['format'] ))
        
        args = {'input':disc.path, \
                'output':output_filename, \
                'title':title['title'], \
        }
        
        subtitles = []
        if settings['burn_foreign_subs']:
            subtitles.append('scan')
            args.update({'subtitle-forced':'scan', \
                        'subtitle-burn':'scan', \
            })
        
        sub_langs = settings['sub_langs']
        if len(sub_langs) > 0:
            for lang in sub_langs:
                track = _lowest_match(title['subtitles'], lang)
                if track:
                    subtitles.append(track)
                
        if len(subtitles) > 0:
            subtitle_string = ','.join(subtitles)
            args['subtitle'] = subtitle_string

        return args

# Returns the lowest track number that matches the language.
# There might be multiple tracks of the same language (e.g. director's commentary).
# Usually the first (lowest number) is the regular subtitles
def _lowest_match(d, value):
    tracks = d.keys()
    tracks.sort()
    for track in tracks:
        if d[track] == value:
            logger.debug("Found %s language subtitle as track %s" %(value, track))
            return track
            
    logger.warning("Didn't find a %s language subtitle track, ignoring\n" %value)
        
def get_disc_infos(handbrake, input_dir):
    # Intelligently pick which files/folders to encode just from analyzing the
    # 'root' input folder.
    # If a folder contains any VALID_FOLDER_FILES types of files, it's probably a
    # "video_ts" type of folder and we should encode it. If it's a VALID_FILES (like
    # an iso), just encode it directly.
    dirs = []
    for dirpath, dirnames, filenames in os.walk(input_dir):
        for filename in filenames:
            (root, ext) = os.path.splitext(filename)
            if ext.lower() in VALID_FILES:
                dirs.append(os.path.join(dirpath,filename))
        if dvd_file_in_dir(dirpath):
            (dirroot, dirtail) = os.path.split(dirpath)
            # If this is a video_ts folder, actually encode one level up so that
            # the output video is properly named.
            if dirtail.lower() == 'video_ts':
                dirs.append(dirroot)
            else:
                dirs.append(dirpath)

    if len(dirs) is 0:
        dirs = [input_dir]
        
    discs = []
    for dir in dirs:
        disc = handbrake.get_disc_info(dir)
        if disc:
            discs.append(disc)
    return discs

def dvd_file_in_dir(input_dir):
    files = os.listdir(input_dir)
    for filename in files:
        (root, ext) = os.path.splitext(filename)
        if ext.lower() in VALID_FOLDER_FILES:
            return True

    
def parse_options():
    p = optparse.OptionParser(usage = USAGE, version="%prog "+VERSION)
    
    required_group = optparse.OptionGroup(p, "Required Options")
    required_group.add_option('--source-dir', metavar='<dir>', help="Source directory to scan")
    p.add_option_group(required_group)

    useful_group = optparse.OptionGroup(p, "Useful Options")
    useful_group.add_option('--encode', action="store_true", help="Actually encode the titles instead of displaying info")
    useful_group.add_option('--output-dir', metavar='<dir>', help="Destination directory (defaults to the source)")
    useful_group.add_option('--extension', default = DEFAULT_FORMAT, metavar='(mp4/mkv)', help="The extension to give all encoded videos")
    useful_group.add_option('--handbrake-args', default = "", metavar='<"args">', help="All of the encoding arguments to be passed-through "\
        +"to handbrake, surrounded by quotes. (Note that HandBrake CLI only supports built-in presets!)")
    p.add_option_group(useful_group)

    subtitle_group = optparse.OptionGroup(p, "Subtitle Options")
    subtitle_group.add_option('--native-lang', default=DEFAULT_LANG, metavar='<lang>', help="Native Language (e.g. eng)")
    subtitle_group.add_option('--burn-foreign-subs', action="store_true", help="Burn-in any foreign language subtitles")
    subtitle_group.add_option('--sub-langs', metavar='<lang1,lang2>', help="Comma-separated list of soft subtitle languages to include (e.g. eng,fra)")
    p.add_option_group(subtitle_group)

    tweak_group = optparse.OptionGroup(p, "Tweaker Options")
    tweak_group.add_option('--handbrake-path', metavar='<path>', help="Path to HandBrake CLI executable")
    tweak_group.add_option('--threshold', default = DEFAULT_THRESHOLD, metavar='<decimal>', help="Sensitivity threshold for TV episode detection")
    tweak_group.add_option('--duplicate-detection', action="store_true", help="Try to filter out duplicate titles")
    tweak_group.add_option('--tv-detection', action="store_true", help="Try to only encode TV episodes")
    tweak_group.add_option('--verbose', action="store_true", help="Verbose output")
    p.add_option_group(tweak_group)
    
    options, arguments = p.parse_args()
    
    if options.verbose:
        logger.setLevel(logging.DEBUG)
    
    if not options.source_dir:
        p.print_help()
        p.error("--source-dir is required")
    
    if not options.output_dir:
        options.output_dir = options.source_dir
    


    return(options, arguments)

    
def get_handbrake_path(given_path):
    (handbrake_exe,handbrake_path) = get_default_platform_handbrake_name_path()

    # If a path was provided in the command line, only try that
    if (given_path and os.path.isfile(given_path)):
        return given_path

    # Look in the current directory
    dir = os.path.join(os.getcwd(),handbrake_exe)
    if os.path.isfile(dir):
        return dir
        
    # Look in default handbrake directory
    dir = os.path.join(handbrake_path,handbrake_exe)
    if os.path.isfile(dir):
        return dir

    raise Exception, "\nCouldn't find HandBrake CLI. Please download it if necessary from 'http://handbrake.fr/downloads2.php' \nand specify the path using '--handbrake-path'"
    
def get_default_platform_handbrake_name_path():
    plat = platform.system()

    if plat == 'Darwin':
        return ('HandbrakeCLI', '/Applications')
    elif plat == 'Windows':
        return ('HandBrakeCLI.exe',os.path.join(os.environ.get('PROGRAMFILES'),'Handbrake'))
    else:
        return ('HandBrakeCLI', '/usr/bin')
    
def main():
    options, arguments = parse_options()
    
    sub_langs = []
    if options.sub_langs:
        sub_langs = options.sub_langs.split(',')
    
    try:
        valid_handbrake_path = get_handbrake_path(options.handbrake_path)
    except Exception, err:
        logger.error(err)
        logger.debug(traceback.format_exc())
        sys.exit()
        
    if not options.encode:
        logger.info("\nINFO MODE: NOTHING WILL BE ENCODED (add --encode to actually encode)\n")
    
    encode_settings = {
                'input': options.source_dir, \
                'output_dir': options.output_dir, \
                'handbrake_path': options.handbrake_path, \
                'threshold': options.threshold, \
                'native_lang': options.native_lang, \
                'burn_foreign_subs': options.burn_foreign_subs, \
                'sub_langs': sub_langs, \
                'format': options.extension, \
                'simulate': not options.encode, \
                'duplicate_detection': options.duplicate_detection, \
                'tv_detection': options.tv_detection, \
                'verbose': options.verbose, \
                'passthrough_args': shlex.split(options.handbrake_args), \
               }
    handbrake = Handbrake(valid_handbrake_path)
    
    logger.info("Scanning %s for suitable titles to encode" %encode_settings['input'])
    discs = get_disc_infos(handbrake, encode_settings['input'])
    
    if len(discs) > 0:
        logger.info("Found suitable titles!\n")
        if not options.encode:
            logger.info("The following handbrake commands will be run when the --encode option is set:\n")
    
    for disc in discs:
        logger.debug("Found disc: %s\n" %str(disc))
        encode_disc_with_settings(disc, handbrake, encode_settings)
        
    if not options.encode and not options.verbose:
        logger.info("\nWARNING: Some titles might have been purposefully skipped due to filtering. Add --verbose for more details and a listing of any skipped titles and double-check that all desired titles are being encoded.")
        
if __name__ == "__main__":
    main()
