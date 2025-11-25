+------------------------------------------------------------+
| 🎵 Ghost Layers Media Player |
| Winamp-style audio & video player, black & green |
+------------------------------------------------------------+

Features:
  • Play MP3, WAV, MP4 files
  • Video popup window for video files
  • Dark UI: black background, neon green text
  • Controls: PLAY | PAUSE | STOP | BACK | NEXT
  • Shuffle & Repeat modes
  • Track time elapsed and remaining
  • Scrubbing slider + volume control
  • Playlist panel (50% width)
  • Waveform visualization at bottom
  • Fixed-size, Winamp-style layout

Tech Stack:
  Frontend/UI: PyQt5
  Audio/Video Backend: python-vlc
  Waveform: librosa + numpy
  Optional: pillow, matplotlib


Installation (Windows):
  1) Install Python modules:
     pip install PyQt5 python-vlc librosa numpy
     (Optional: pip install pillow matplotlib)

  2) Install VLC Desktop version:
     https://www.videolan.org/vlc/
     Add VLC folder to System PATH, e.g.:
     C:\Program Files\VideoLAN\VLC

  3) Test VLC linkage:
     python -c "import vlc; print(vlc.libvlc_get_version())"

Run the Player:
  python main.py

Supported Formats:
  Audio: .mp3, .wav, .flac
  Video: .mp4, .avi, .mkv
  > Video opens in separate popup window

Common Issues:
  - No module named vlc: pip install python-vlc
  - VLC window crashes: ensure 64-bit VLC matches Python
  - Black video screen: try DirectX mode
  - Audio glitches: check file format

Development Notes:
  - Fixed window size (Winamp-like)
  - Playlist occupies 50% top area
  - Waveform spans full width at bottom
  - Buttons use text labels, no emojis

Future Upgrades:
  • Spectrum equalizer
  • Skin/theme support
  • Keyboard hotkeys
  • Multi-track queue management

Author:
  Ghost Layer Media Player Project
  Designed by Pauly Thimmins
  Developed with ChatGPT (GPT-5.1)

License:
  Private use only. Contact author for redistribution.
+------------------------------------------------------------+