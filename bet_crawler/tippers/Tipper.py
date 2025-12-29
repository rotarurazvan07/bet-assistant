import threading

from bet_crawler.tippers.impl.FootballBettingTipsTipper import FootballBettingTipsTipper
from bet_crawler.tippers.impl.FootyStatsTipper import FootyStatsTipper
from bet_crawler.tippers.impl.FreeSuperTipper import FreeSuperTipper
from bet_crawler.tippers.impl.FreeTipsTipper import FreeTipsTipper
from bet_crawler.tippers.impl.OLBGTipper import OLBGTipper
from bet_crawler.tippers.impl.PickWiseTipper import PickWiseTipper
from bet_crawler.tippers.impl.PredictzTipper import PredictzTipper
from bet_crawler.tippers.impl.WhoScoredTipper import WhoScoredTipper
from bet_crawler.tippers.impl.WinDrawWinTipper import WinDrawWinTipper


class Tipper:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def _update_match_callback(self, match_name, match_date, tip=None, score=None, probability=None):
        self.db_manager.update_match(match_name, match_date, tip, score, probability)

    def get_tips(self):
        tippers = [
            WhoScoredTipper(self._update_match_callback),
            # FreeSuperTipper(self._update_match_callback),
            # WinDrawWinTipper(self._update_match_callback),
            # PickWiseTipper(self._update_match_callback),
            # FootyStatsTipper(self._update_match_callback),
            # FreeTipsTipper(self._update_match_callback),
            # OLBGTipper(self._update_match_callback),
            # PredictzTipper(self._update_match_callback),
            # FootballBettingTipsTipper(self._update_match_callback)
        ]

        threads = []
        for i in range(len(tippers)):
            threads.append(threading.Thread(target=self._get_tips_helper, args=(tippers[i],)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def _get_tips_helper(self, tipper_obj):
        tipper_obj.get_tips()
