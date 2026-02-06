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

        self.target_pids = None
        self.restore_delay = 1

        self._original_volumes = {}
        self._restore_timer_start = None

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

    def _is_source_playing(self) -> bool:
        for session in self._get_sessions():
            if not session.Process:
                continue
            if session.Process.pid != self.source_pid:
                continue

            meter = session._ctl.QueryInterface(IAudioMeterInformation)
            if meter.GetPeakValue() > self.threshold:
                return True
        return False

    def monitor(self):
        self.running = True
        was_playing = False

        while self.running:
            playing = self._is_source_playing()

            if playing:
                self._restore_timer_start = None
                if not was_playing:
                    self._apply_effect(True)

            else:
                if was_playing:
                    self._restore_timer_start = time.time()

                if self._restore_timer_start is not None:
                    elapsed = time.time() - self._restore_timer_start
                    if elapsed >= self.restore_delay:
                        # финальная проверка
                        if not self._is_source_playing():
                            self._apply_effect(False)
                            self._restore_timer_start = None

            was_playing = playing
            time.sleep(0.1)

    def start(
        self,
        source_pid: int,
        use_ducking: bool,
        target_pids: set | None,
        restore_delay: int
    ):
        self.source_pid = source_pid
        self.use_ducking = use_ducking
        self.target_pids = target_pids
        self.restore_delay = restore_delay

        self.running = True
        threading.Thread(target=self.monitor, daemon=True).start()

    def stop(self):
        self.running = False
        self._restore_timer_start = None
        self._apply_effect(False)