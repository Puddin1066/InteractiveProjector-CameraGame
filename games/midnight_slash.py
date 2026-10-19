"""
Lynx Midnight Slash: the spookier Spooky Slash. Same hand-tracking game, new
look and rules: a witch-hat Lincoln Lynx, green-and-gold midnight art and
playful spooky music, and timed three-minute rounds for one to five children
on one team. The throws speed up as the round goes on, with "Witching Hour"
frenzies; skulls cost points instead of ending the round. After the score and
the best score of the day, the menu comes back for the next group.

The art, sounds and rule changes are in web/midnight_slash, which is served
over web/spooky_slash, so anything not themed comes from Spooky Slash.

    python play.py midnight-slash [--layout wall] [--blades shadows] [--debug]

The options are Spooky Slash's; see games/spooky_slash.py.
"""
from games import spooky_slash

THEME_ROOT = spooky_slash.WEB_ROOT.parent / "midnight_slash"

if __name__ == "__main__":
    spooky_slash.main((THEME_ROOT, spooky_slash.WEB_ROOT), __doc__)
