import threading

from impl.FootyStatsTipper import FootyStatsTipper
from impl.ForebetTipper import ForebetTipper
from impl.FreeSuperTipper import FreeSuperTipper
from impl.FreeTipsTipper import FreeTipsTipper
from impl.OLBGTipper import OLBGTipper
from impl.PickWiseTipper import PickWiseTipper
from impl.WhoScoredTipper import WhoScoredTipper
from impl.WinDrawWinTipper import WinDrawWinTipper


class Tipper:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def _add_tip_callback(self, tip, match_name, match_time):
        self.db_manager.add_or_update_tip(tip, match_name, match_time)

    def get_tips(self):
        tippers = [
            WhoScoredTipper(self._add_tip_callback),
            ForebetTipper(self._add_tip_callback),
            FreeSuperTipper(self._add_tip_callback),
            WinDrawWinTipper(self._add_tip_callback),
            PickWiseTipper(self._add_tip_callback),
            FootyStatsTipper(self._add_tip_callback),
            FreeTipsTipper(self._add_tip_callback),
            OLBGTipper(self._add_tip_callback)
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
