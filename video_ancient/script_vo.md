# Voice-over script — "How Ancient Humans Survived" (46.0 s, 9:16)

Har beat ka apna **slot** hai. Narration file `audio_sh/beatNN.wav` (48 kHz, mono
ya stereo) us beat ke `start` par baithti hai, is liye line beat se lambi nahi
honi chahiye. On-screen caption wahi line hai jo boli ja rahi hai (Roman), voice
ke liye Urdu script di hui hai taake Pakistani lehja sahih aaye.

| # | start | slot | Roman (caption = VO) | Urdu script (voice) |
|---|---|---|---|---|
| 1 | 0.30 s | 4.30 s | Bees hazaar saal pehle. Na ghar, na kapde, na khane ka bharosa. | بیس ہزار سال پہلے۔ نہ گھر، نہ کپڑے، نہ کھانے کا بھروسہ۔ |
| 2 | 4.60 s | 4.60 s | Har subah ek hi sawal — zinda raho ge ya nahi? | ہر صبح ایک ہی سوال — زندہ رہو گے یا نہیں؟ |
| 3 | 9.20 s | 5.10 s | Phir bijli ne aag di. Aur insaan ne usko dost bana liya. | پھر بجلی نے آگ دی۔ اور انسان نے اُس کو دوست بنا لیا۔ |
| 4 | 14.30 s | 4.30 s | Aag yaani garmi. Aag yaani roshni. Aur darinde door. | آگ یعنی گرمی۔ آگ یعنی روشنی۔ اور درندے دور۔ |
| 5 | 18.60 s | 4.50 s | Pathar toda… aur hathiyaar bana. Shikaar aasan hua. | پتھر توڑا… اور ہتھیار بنا۔ شکار آسان ہوا۔ |
| 6 | 23.10 s | 4.70 s | Akela insaan kamzor tha. Magar jhund mein… woh khatarnaak tha. | اکیلا انسان کمزور تھا۔ مگر جھنڈ میں… وہ خطرناک تھا۔ |
| 7 | 27.80 s | 4.40 s | Janwar ki khaal jacket ban gayi. Gufa ghar ban gaya. | جانور کی کھال جیکٹ بن گئی۔ غار گھر بن گیا۔ |
| 8 | 32.20 s | 4.50 s | Aur sabse bada hathiyaar? Zubaan. Sikhana shuru hua. | اور سب سے بڑا ہتھیار؟ زبان۔ سکھانا شروع ہوا۔ |
| 9 | 36.70 s | 4.50 s | Beej boya… aur bhookh kam hui. | بیج بویا… اور بھوک کم ہوئی۔ |
| 10 | 41.20 s | 4.80 s | Hum wahi insaan hain. Sirf tools badle hain. | ہم وہی انسان ہیں۔ صرف اوزار بدلے ہیں۔ |

## Delivery notes

- Easy Urdnglish, thora dheema, har line ke aakhir mein chhota pause — tension
  beat 2 aur 6 par zyada, beat 10 par sukoon.
- Beat 5 ke "pathar toda" ke baad chhota sa gap rakhein: wahan chaar strike SFX
  baje hain (0.75 / 1.55 / 2.35 / 3.15 s).
- Har file 48 kHz, peak ≤ −3 dBFS, mono ya stereo. `python audio_an.py` khud
  voice ko −1.5 dBFS par normalize karke music 8 dB neeche duck karta hai.
