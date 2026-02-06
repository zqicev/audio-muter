import time
import threading

from pycaw.pycaw import (
    AudioUtilities,
    ISimpleAudioVolume,
    IAudioMeterInformation
)


class AudioController:
    def __init__(self):
        self.running = False
        self.source_pid = None

        self.threshold = 0.02
        self.use_ducking = False
        self.duck_volume = 0.2

        # если None - глушим всё
        # если set(pid) - глушим только их
        self.target_pids = None

        self._original_volumes = {}

    def _get_sessions(self):
        return AudioUtilities.GetAllSessions()

    def _should_affect(self, pid: int) -> bool:
        if pid == self.source_pid:
            return False

        if self.target_pids is None:
            return True

        return pid in self.target_pids

    def _apply_effect(self, active: bool):
        for session in self._get_sessions():
            if not session.Process:
                continue

            pid = session.Process.pid
            if not self._should_affect(pid):
                continue

            volume = session._ctl.QueryInterface(ISimpleAudioVolume)

            if self.use_ducking:
                if active:
                    if pid not in self._original_volumes:
                        self._original_volumes[pid] = volume.GetMasterVolume()
                    volume.SetMasterVolume(self.duck_volume, None)
                else:
                    original = self._original_volumes.get(pid, 1.0)
                    volume.SetMasterVolume(original, None)
            else:
                volume.SetMute(active, None)

        if not active:
            self._original_volumes.clear()

    def monitor(self):
        self.running = True
        was_playing = False

        while self.running:
            playing = False

            for session in self._get_sessions():
                if not session.Process:
                    continue
                if session.Process.pid != self.source_pid:
                    continue

                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                if meter.GetPeakValue() > self.threshold:
                    playing = True
                    break

            if playing and not was_playing:
                self._apply_effect(True)

            if not playing and was_playing:
                self._apply_effect(False)

            was_playing = playing
            time.sleep(0.1)

    def start(self, source_pid: int, use_ducking: bool, target_pids: set | None):
        self.source_pid = source_pid
        self.use_ducking = use_ducking
        self.target_pids = target_pids

        threading.Thread(target=self.monitor, daemon=True).start()

    def stop(self):
        self.running = False
        self._apply_effect(False)