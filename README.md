Basic versionings
0.0.1: initial release

0.0.2
- fixed issue where "?" in village name couldn't be parsed
- fixed weekly reset of topfarm data
- fine tuned weekly topfarm data visualization

0.0.3
Improvements to topfarm page
- removed zero farm per hour datapoint
- fixed issue of duplicate data when user was in top10 farmers
- added option to look back historic weekly farm data

0.0.4
Fixes:
- fixed a bug where new trade route imports added to the existing routes table instead of updating the list
- fixed a bug where barracks/stables/workshop training times were wrongly calculated with building lvls
- fixed a bug where some roman troops had wrong cost values in the csv
- fixed a bug where alliance bonus values were wrong on the alliance info page
- fixed a bug where only one trade route was added when there are multiple present
- fixed a bug where village groupings were not parsed correctly
- fixed a bug where alliance bonuses were not calculated into troop production times
- fixed a bug where after the response info of the initial parsing buttons are not visible
- fixed a bug where on the account overview page only one village was visible per village groups

Improvements:
- added a grand total "all resourses sum" number to the net production table
- added a village building and resource field parser

Errors found:
- found an error where in the buildings menu the "sort to plan" deletes entries - need to check further


Improvements still needed:
- add a delete village template button
- set the field type distribution on the right side from the parsed res field data
- add an "inactive wh/granary fill time" table. Inactive means no new queues or parties, dont count those in, but calculate with trade routes and troops present
- add a "troops in villages" page parser, calculate crop consumption per villa from that - !!!IMPORTANT!!! - multi tribe troops (+ animals) are possible, that could break shit
- add a "time until accountwide negative crop" calculation from current net production + queues
- add an option to select hero items to adjust troop production time - queue cost