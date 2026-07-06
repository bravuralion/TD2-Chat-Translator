<p align="center">
  <img src="https://img.ttsk.ngo/images/2024/07/31/PIS-Logo.jpg" alt="PIS Logo">
</p>

Hello everyone,

You may have seen my last post with Desktranslate, which can be used to translate the chat using OCR ([link](https://td2.info.pl/english-boards/automatic-translation-of-the-ingame-chat-(and-more)/)). On this post there was the following comment:

<p align="center">
  <blockquote>
    Maybe extracting text messages from the TD2 logs would be a better move?
  </blockquote>
</p>

I followed up on this idea and it worked. I am currently in the process of writing a program that can run alongside the game and instantly extract and translate the chat data from the log. The aim is to make the program as simple as possible and not to interfere while playing Train Driver 2.

Operation is very simple: start the simulator, start the translator, and just specify where the TD2 logs are to be stored as well as the target language to which the translation is to be made. The program then runs in the background and the translated text appears in a dedicated window:

<p align="center">
  <img src="https://img.ttsk.ngo/images/2026/07/06/2026-07-06-11_25_36-TrainDriver2.png">
</p>

The program currently automatically filters out system messages and emote messages such as ++ o/ etc. so that only the actual chat is translated.  **chat in the app can be selected and copied to be able to paste it elsewhere!**

You can choose between two translation engines at any time in the app: **DeepL** (the default, generally the best translation quality) and **Google Translate** (a free alternative). The translated text is still far from perfect - that's partly down to the engines themselves and, of course, the way people write in chat - but it helps players understand each other a lot better than no translation at all.

**Update:** ChatGPT/OpenAI support has been removed. To keep things secure, DeepL translations no longer go directly from your PC to DeepL - instead they're routed through a small backend. Nothing changes in how you use the app.

The translator now also automatically recognizes station/scenery names (e.g. *Chełmik Wołowski*, *Cibórz Las*) and common short dispatcher phrases (*Przyjąłem*, *Tak*, *Nie*, *szlak zajęty*, ...) and keeps them correct instead of letting machine translation mangle them.

<p align="center">
  <b>The following languages are currently supported:</b><br>
  English, German, Polish, French, Spanish, Italian, Dutch, Portuguese, Greek, Swedish, Danish, Finnish, Norwegian, Czech, Slovak, Hungarian, Romanian, Bulgarian, Croatian, Serbian, Slovenian, Estonian, Latvian, Lithuanian, Maltese, and Russian.
</p>

The app is in an early alpha stage and I am still looking for testers who can test the app. I am planning a first release at the end of this week or next week for everyone in beta. If you are interested in testing the program, please contact me on Mattermost or come to my Discord server. I am currently working on it daily. When a public version is available, this post will be updated here and the link will be available here.
