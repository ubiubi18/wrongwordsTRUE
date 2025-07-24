# wrongwordsTRUE

How to run

python3 find_wrongwords.py           # uses epoch 166
python3 find_wrongwords.py 170       # overrides epoch on the fly

You’ll see a live log like:

[1/3] Fetching flip list for epoch 166 …
[2/3] 1046 flips found. Scanning for wrongWords …
   1/1046  0xabc…  wrongWords=False
   2/1046  0xdef…  wrongWords=True
   …
[3/3] Summary for epoch 166
address                                wrongWordsCount
--------------------------------------------------
0xdef…                               3  **>1**
0x123…                               2  **>1**
0xabc…                               0
…

Identities with more than one offending flip are marked with **>1**.
Feel free to tweak sleep intervals or add file output if you need it saved.
