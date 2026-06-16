import sounddevice as sd
import numpy as np

duration = 5  # seconds
fs = 44100

print("Recording for 5 seconds...")
recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
sd.wait()

volume_norm = np.linalg.norm(recording) / len(recording)
print("Volume Level:", volume_norm)
