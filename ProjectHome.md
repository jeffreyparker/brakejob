### News ###
**(6/10/10) Version 0.1.1 released**
  * Improved support for finding the HandBrakeCLI binary. Also works cross-platform!
  * OSX and Linux versions should actually work now
  * Added --version option

### What is BrakeJob ###

BrakeJob is a command line (CLI) "wrapper" for HandBrakeCLI that adds a few features missing from HandBrake, most notably smart batch encoding of TV show discs and batch subtitle support.

BrakeJob scans the specified input folder for all subfolders containing DVD
images. Each DVD is intelligently scanned to filter out all the "junk" titles (menus, special features, duplicate titles, etc). Each of the remaining titles is encoded with HandBrakeCLI using the passed-in encoding settings.

Besides the standard HandBrake settings, BrakeJob also supports specifying
subtitle encoding. For example, you can specify that every encoding have any
foreign language subtitles burned into the video, and the English subtitles
to be toggleable on/off (when using the MKV container)

BrakeJob is written in Python and designed to be cross-platform. Any platform can download the source and run 'python brakejob.py', or Windows users can use the binary version.

### BrakeJob is still in early-development and may be missing key features. ###
Encoding a directory of TV show DVDs with subtitle support **should** work as stated.

You must put the HandBrakeCLI binary in the same directory as BrakeJob, or specify its path with the --handbrake-path option. You can download it at http://handbrake.fr/downloads2.php

### Example Usage ###
Encode a directory using the Normal preset, but also add detelecine and decomb, using mkv container, burn-in any foreign subs and include the English langauge soft-subs (toggleable on/off)

brakejob.exe --source-dir "C:\Users\Jeff\Documents\DVDFab\FullDisc" --native-lang eng --burn-foreign-subs --sub-langs eng --extension mkv --handbrake-args "-Z Normal -f mkv --detelecine --decomb" --encode



### Do we really need yet another HandBrake wrapper script? ###
Probably not, but I couldn't find any existing ones that intelligently handled TV shows, supported subtitles, and were cross platform (there are **tons** of bash/bat scripts out there)

Plus, I'll jump at any chance I get to code in Python.