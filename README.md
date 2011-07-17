**INTRODUCTION**

dockutil is a command line utility for managing Mac OS X dock items.
It is currently writting in Python and makes use of plistlib module included in Mac OS X.
- Compatible with Mac OS X 10.4.x thru 10.6.x. 
- Add, List, Move, Find, Remove Dock Items
- Supports Applications, Folders, Stacks, URLs. 
- Can act on a specific dock plist or every dock plist in a folder of home directories

**LICENSE**

[Apache 2](http://www.apache.org/licenses/LICENSE-2.0)

**USAGE**

usage:     dockutil -h
usage:     dockutil --add <path to item> | <url> [--label <label>] [ folder_options ] [ position_options ] [ plist_location_specification ]
usage:     dockutil --remove <dock item label> [ plist_location_specification ]
usage:     dockutil --move <dock item label>  position_options [ plist_location_specification ]
usage:     dockutil --find <dock item label> [ plist_location_specification ]
usage:     dockutil --list [ plist_location_specification ]

position_options:
  --replacing <dock item label name>                            replaces the item with the given dock label or adds the item to the end if item to replace is not found
  --position [ index_number | beginning | end | middle ]        inserts the item at a fixed position: can be an position by index number or keyword
  --after <dock item label name>                                inserts the item immediately after the given dock label or at the end if the item is not found
  --before <dock item label name>                               inserts the item immediately before the given dock label or at the end if the item is not found
  --section [ apps | others ]                                   specifies whether the item should be added to the apps or others section

plist_location_specifications:
  <path to a specific plist>                                    default is the dock plist for current user
  <path to a home directory>
  --allhomes                                                    attempts to locate all home directories and perform the operation on each of them
  --homeloc                                                     overrides the default /Users location for home directories

folder_options:
  --view [grid|fan|list|automatic]                              stack view option
  --display [folder|stack]                                      how to display a folder's icon
  --sort [name|dateadded|datemodified|datecreated|kind]         sets sorting option for a folder view

Examples:
  The following adds TextEdit.app to the end of the current user's dock:
           dockutil --add /Applications/TextEdit.app

  The following replaces Time Machine with TextEdit.app in the current user's dock:
           dockutil --add /Applications/TextEdit.app --replacing 'Time Machine'

  The following adds TextEdit.app after the item Time Machine in every user's dock on that machine:
           dockutil --add /Applications/TextEdit.app --after 'Time Machine' --allhomes

  The following adds ~/Downloads as a grid stack displayed as a folder for every user's dock on that machine:
           dockutil --add '~/Downloads' --view grid --display folder --allhomes

  The following adds a url dock item after the Downloads dock item for every user's dock on that machine:
           dockutil --add vnc://miniserver.local --label 'Mini VNC' --after Downloads --allhomes

  The following removes System Preferences from every user's dock on that machine:
           dockutil --remove 'System Preferences' --allhomes

  The following moves System Preferences to the second slot on every user's dock on that machine:
           dockutil --move 'System Preferences' --position 2 --allhomes

  The following finds any instance of iTunes in the specified home directory's dock:
           dockutil --find iTunes /Users/jsmith

  The following lists all dock items for all home directories at homeloc in the form: item<tab>path<tab><section>tab<plist>
           dockutil --list --homeloc /Volumes/RAID/Homes --allhomes


Notes:
  When specifying a relative path like ~/Documents with the --allhomes option, ~/Documents must be quoted like '~/Documents' to get the item relative to each home

Bugs:
  Names containing special characters like accent marks will fail


**LIMITATIONS AND DEPENDENCIES**

Requires plistlib

