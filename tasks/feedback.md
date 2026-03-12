General rules:
i dont care about backward compatibily unless stated otherwise.
Refactor as much as you can if that improves the code, the point is to have clean, concerc sepaarated and modular code.

1. In slips, add a way to delete slips that have no results already. - ie all legs pending
2. In slips, show unit bets per slip, compact the slip cards, they are too wide for their info - maybe a grid with multiple on row
3. in smart builder, highlight legs that are already present in pending slips (by result_url) so user can eliminate them so it doesnt duplicate them via excluded urls.
4. dont enfroce default profiles all the time, only if profiles folder doesnt exist or is empty. ie if there is at least one profile, dont enforce.
5. add more clues when things are loading and block input where needed - and give more clues when things are happening, on screen small but accesible to look at, what needs blocking like pull database should block, what not, unify a small indicator somewhere on top to identify whats going on, with a text box underneath that tells the actions that s happening, happened.
10. Legs in Slips view to show datetime, and to show live score if possible (via the result_url) - only on pending slips, settled shouldnt be touched. - so a running thread that constantly checks and updates ?
11. in profiles, add how many times to generate in the run, insead of run daily check, put number box if > 0 it runs for that many times inside main.py generate
12. in slip builder, when a profile is loaded, but something is changed in it, switch it to a custom/independent/live CUSTOM profile. CUSTOM will be used for all bets placed by user independently.. this is to separate manual modifications that dont need to be saved (i.e this profile is purely in memory, only saved when use explictly saves it with whatever name. Analytics should know to separte between indepedent manual bets and profile-made bets.
13. check if excluded_urls is ONLY applied inside the slip builder tab, not on the automatic generator! its important, excluded urls via the x buttons on the legs card is just for manually creating bets.
14. add a "reset excluded matches" button in the slip builder that resets the matches manually excluded.
15. analytics tab graphs are badly represetned, just maybe start from the most important ones like balance, wins, etc, i think we complicated it. and the graphs dont work, i have bars graphs that also draw lines.. it should filter both on all profiles or per profile.
16. built-in dashboard thread that pull the artifact? (like what pull Update does, but regularly at a configurable hour) that verify results ? (could be well for live scores also!) - here i want pros and cons, and i will choose if I want this approach, but might be better contained like this! This will come with a Dashboard configuration tab to set things up etc.
17. If possible, separate concers in dashboard, i mean rendering stuff is one thing, like the html, logic in other functions, etc, i want as clean sepration as possible.
18. Odds that have missing info inside, when others odds that can fill them arrive in add_match in MatchesManager, seems it has no effect, the odds have missing fields. (example i save a match with odds for 1 x 2, but down the line i get odds for btts, those wont update correctly and im left only with 1 x 2)
19. datetime still not ok when enriching, need better timezones