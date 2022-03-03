**INTRODUCTION**

dockutil is a command line utility for managing macOS dock items.
It is currently written in Swift.
- Compatible with macOS Big Sur & Monterey (use 2.x version for older
  OSes)
- Add, List, Move, Find, Remove Dock Items
- Supports Applications, Folders, Stacks, URLs. 
- Can act on a specific dock plist or every dock plist in a folder of home directories

**LICENSE**

[Apache 2](http://www.apache.org/licenses/LICENSE-2.0)

**CHANGELOG**

Version 3.0.0
- Rewrite in Swift for macOS 12.3 compatibility
- Feature compatibility with previous version
- Find, Add, Remove by bundle identifier, URL or path
- Allow multiple actions in single run (add, remove can be combined and specified multiple times)

Version 2.0.5
- 10.12 fix for Dock restart
- Add and remove spacer tiles

Version 2.0.4
- Allow removal by app bundle identifier (credit to Yoann Gini)
- Bug fixes for plist quoting (credit to VitosX)

Version 2.0.3
- Wait for dock to be setup by Apple before modifying (useful for first login scripts)

Version 2.0.2
- Bug Fix for 10.9.x

Version 2.0.1

- Yosemite compatibility
- Support for multiple removals

Version 2.0.0

- Remove restart of cfprefsd in favor of using defaults
- Bumped to version 2 because some backend changes may break compatibility with older OS versions
- Please test and report any issues

Version 1.1.4

- Restart cfprefsd before restarting Dock to ensure settings are read

Version 1.1.3

- fix issue with missing labels and removals

Version 1.1.2

- fix issue with replacing a url dock item
- add legacy support --hupdock option for backward compatibility
- fix paths with spaces when passing full path to plist


Version 1.1

- fixes many issues with paths (should now work with Default User Template)
- adds option to not restart the dock (--no-restart)
- fixes issue where item would be added multiple times
(use --replacing to update an existing item)
- resolves deprecation warnings
- adds option to remove all items (--remove all)
- fix issue with removals when a url exists in a dock
- adds option --version to output version


**USAGE**

    usage:     dockutil -h
    usage:     dockutil --add <path to item> | <url> [--label <label>] [ folder_options ] [ position_options ] [--no-restart] [ plist_location_specification ]
    usage:     dockutil --remove <dock item label> | <app bundle id> | all | spacer-tiles [--no-restart] [ plist_location_specification ]
    usage:     dockutil --move <dock item label>  position_options [ plist_location_specification ]
    usage:     dockutil --find <dock item label> [ plist_location_specification ]
    usage:     dockutil --list [ plist_location_specification ]
    usage:     dockutil --version

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
      --view [grid|fan|list|auto]                                   stack view option
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

      The following adds Firefox after Safari in the Default User Template without restarting the Dock
               dockutil --add /Applications/Firefox.app --after Safari --no-restart '/System/Library/User Template/English.lproj'

      The following adds a spacer tile in the apps section after Mail
               dockutil --add '' --type spacer --section apps --after Mail

      The following removes all spacer tiles
               dockutil --remove spacer-tiles

    Notes:
      When specifying a relative path like ~/Documents with the --allhomes option, ~/Documents must be quoted like '~/Documents' to get the item relative to each home
      When specifying paths in macOS 11 Big Sur or higher note that the path to applications is /System/Applications so to add TextEdit.app :
              dockutil --add /System/Applications/TextEdit.app



**LIMITATIONS AND DEPENDENCIES**


