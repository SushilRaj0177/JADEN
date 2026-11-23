# Real data: long-term-care office addresses (Ministry of Health, Labour and Welfare)

Source: 介護サービス情報公表システム オープンデータ (data as of 2026年６月末時点, CC BY). Rows used: every office row with an address: **223,161**. Processed in 95 s on 4 processes.

Every row is a real office, so the right municipality outcome is always `correct`.

## The address exactly as typed (often without prefecture or municipality)

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| correct | 218,428 | 97.88% |
| ambiguous, truth listed | 4,125 | 1.85% |
| rejected: MALFORMED | 292 | 0.13% |
| rejected: UNSUPPORTED | 127 | 0.06% |
| not scored: the typed address and the row's columns name different municipalities | 123 | 0.06% |
| ambiguous, truth not listed | 41 | 0.02% |
| wrong | 13 | 0.01% |
| row carries a municipality code that no longer exists | 12 | 0.01% |
| **all** | 223,161 |  |

## With the row's prefecture and municipality columns put in front where the text lacks them

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| correct | 222,878 | 99.87% |
| not scored: the typed address and the row's columns name different municipalities | 118 | 0.05% |
| rejected: UNSUPPORTED | 95 | 0.04% |
| rejected: MALFORMED | 26 | 0.01% |
| ambiguous, truth listed | 23 | 0.01% |
| row carries a municipality code that no longer exists | 15 | 0.01% |
| wrong | 4 | 0.00% |
| ambiguous, truth not listed | 2 | 0.00% |
| **all** | 223,161 |  |

## Town (of the addresses with the right municipality)

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| town verified | 221,284 | 99.28% |
| town not in the registry | 1,036 | 0.46% |
| no town written | 558 | 0.25% |
| **all** | 222,878 |  |

## Building, floor and room against the 方書 column

Rows whose typed address ends with the text of the 方書 column. The address is resolved with and without that text; the address part must not change.

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| same address, building separated | 47,720 | 95.84% |
| not scored: the 方書 column holds only part of the building text | 1,209 | 2.43% |
| not decidable: the publisher glued a number to the house number | 631 | 1.27% |
| address changes when the building is attached | 104 | 0.21% |
| not scored: the 方書 column holds the house number too | 66 | 0.13% |
| same address, building text dropped | 63 | 0.13% |
| **all** | 49,793 |  |

## The same office listed several times with different spellings

Offices (by 事業所番号) whose rows carry two or more different address strings. Where the strings carry the same numbers, they should get the same house-level match key.

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| all spellings share one key | 9,900 | 85.07% |
| not scored: the spellings carry different numbers (a move, or a typo in the data) | 1,315 | 11.30% |
| spellings get different keys | 366 | 3.14% |
| a spelling could not be keyed | 57 | 0.49% |
| **all** | 11,638 |  |

Of the offices whose spellings carry the same numbers, **95.90%** get one key (9,900 of 10,323).

## Distance from JADEN's offline point to the published coordinates

The published coordinates come from the publishing system's own geocoding, so this is agreement between two systems, not error against a survey.

| JADEN point level | Addresses | Median distance | Within 1 km | Over 20 km |
| :--- | ---: | ---: | ---: | ---: |
| town | 124,200 | 533 m | 73.9% | 0.33% |
| chome | 96,315 | 157 m | 98.5% | 0.51% |

## Precision reached

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| house | 190,379 | 85.42% |
| unit | 17,448 | 7.83% |
| block | 14,877 | 6.67% |
| chome | 108 | 0.05% |
| town | 65 | 0.03% |
| municipality | 1 | 0.00% |
| **all** | 222,878 |  |

## Examples of what is not `correct`

**as typed: ambiguous, truth listed** (4,125)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 新在家125-11リブハウス・アズ1Ｆ | AMBIGUOUS: 新在家125-11リブハウス・アズ1F | the municipality is ambiguous: the text is returned as written, not interpreted |
| 小野町5-89-10 | AMBIGUOUS: 小野町5-89-10 | '小野町' is a municipality and also a town name in 16 other place(s) |
| 船戸1-19-16 | AMBIGUOUS: 船戸1-19-16 | the municipality is ambiguous: the text is returned as written, not interpreted |
| 大字津留字六本松1970-7 | AMBIGUOUS: 大字津留字六本松1970-7 | the municipality is ambiguous: the text is returned as written, not interpreted |
| 玉沢９０番地 | AMBIGUOUS: 玉沢90番地 | Omitted prefecture matches 2 statutory municipalities. |
| 若宮二丁目41番22号 | AMBIGUOUS: 若宮二丁目41番22号 | the municipality is ambiguous: the text is returned as written, not interpreted |

**as typed: rejected: MALFORMED** (292)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 下安原町東1457番地1第2やすはら苑 | MALFORMED: 下安原町東1457番地1第2やすはら苑 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 壱丁目東３６－３エクラシア上尾西 | MALFORMED: 壱丁目東36-3エクラシア上尾西 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 4-4-25やさしえ東辻井 | MALFORMED: 4-4-25やさしえ東辻井 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 605WORKPLACE春田 | MALFORMED: 605WORKPLACE春田 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 中泉御殿703 | MALFORMED: 中泉御殿703 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 奥海印寺多貝垣外17-1 | MALFORMED: 奥海印寺多貝垣外17-1 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |

**as typed: rejected: UNSUPPORTED** (127)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 奈良町32-42階 | UNSUPPORTED: 奈良町32-42階 | no municipality found: the text is returned as written, not interpreted |
| 富山県高岡氏二上町1144-2 | UNSUPPORTED: 富山県高岡氏二上町1144-2 | no municipality found: the text is returned as written, not interpreted |
| 長野1499番地 | UNSUPPORTED: 長野1499番地 | no municipality found: the text is returned as written, not interpreted |
| 徳島県徳s摩市国府町井戸字左ケ池39番地1 | UNSUPPORTED: 徳島県徳s摩市国府町井戸字左ケ池39番地1 | no municipality found: the text is returned as written, not interpreted |
| 長野県郡野沢温泉村大字豊郷4399番地 | UNSUPPORTED: 長野県郡野沢温泉村大字豊郷4399番地 | Administrative entity could not be resolved to a local government code. |
| 宮崎県北諸県三股町大字樺山4836番26 | UNSUPPORTED: 宮崎県北諸県三股町大字樺山4836番26 | no municipality found: the text is returned as written, not interpreted |

**as typed: not scored: the typed address and the row's columns name different municipalities** (123)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 大阪市東住吉区南田辺二丁目12番7号 | ACCEPTED: 大阪府大阪市東住吉区南田辺2丁目12番7号 | Municipality, town and 丁目 verified against official registries. |
| 群馬県みどり市笠懸町西鹿田182番地1 | ACCEPTED: 群馬県みどり市笠懸町西鹿田182番地の1 | Municipality and town verified against official registries. |
| 帯広市西22条南3丁目33-1 | ACCEPTED: 北海道帯広市西二十二条南3丁目33番1号 | Municipality, town and 丁目 verified against official registries. |
| 長崎県東彼杵郡川棚町新谷郷1700-2グループホーム　サンホーム新谷 | ACCEPTED: 長崎県東彼杵郡川棚町新谷郷1700番2号 グループホーム サンホーム新谷 | Municipality and town verified against official registries. |
| 福岡県小郡市大崎７３８－１ | ACCEPTED: 福岡県小郡市大崎738番1号 | Municipality and town verified against official registries. |
| 茨城県水戸市平須町１８２２番地の２２７　原口アパート２号 | ACCEPTED: 茨城県水戸市平須町1822番地の227 原口アパート 2号 | Municipality and town verified against official registries. |

**as typed: ambiguous, truth not listed** (41)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 佐藤１－２６－３２ | AMBIGUOUS: 佐藤1-26-32 | the municipality is ambiguous: the text is returned as written, not interpreted |
| 吉野3丁目5番8号 | AMBIGUOUS: 吉野3丁目5番8号 | Omitted prefecture matches 15 statutory municipalities. |
| 静岡県静岡市岡部町岡部437番地の3 | AMBIGUOUS: 静岡県静岡市岡部町岡部437番地の3 | town '岡部町岡部' is not registered in any ward of 静岡市 |
| 甲5229番地13 | AMBIGUOUS: 甲5229番地13 | the municipality is ambiguous: the text is returned as written, not interpreted |
| 一宮町1566－1 | AMBIGUOUS: 一宮町1566-1 | '一宮町' is a municipality and also a town name in 4 other place(s) |
| 南山３丁目２３番地２７ | AMBIGUOUS: 南山3丁目23番地27 | the municipality is ambiguous: the text is returned as written, not interpreted |

**as typed: wrong** (13)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 久住町６４８２番地 | ACCEPTED: 鹿児島県薩摩川内市久住町6482番地 | municipality deduced from the town name: 鹿児島県薩摩川内市 is the only match in Japan |
| 御車道通清和院口上る東側梶井町457-1 | ACCEPTED: 京都府京都市上京区御車道通清和院口上る東側梶井町457番地の1 | resolved 11 candidate municipalities to 京都府京都市上京区 by town '梶井町' |
| 大阪府堺市緑ヶ丘南町4-2-23グリーンヒルズ2D | ACCEPTED: 大阪府堺市堺区緑ヶ丘南町四丁2番23号 グリーンヒルズ2D | resolved 7 candidate municipalities to 大阪府堺市堺区 by town '緑ヶ丘南町四丁' |
| 舞原344-2あすなろ熊本壱番館 | ACCEPTED: 佐賀県西松浦郡有田町舞原344番2号 あすなろ熊本壱番館 | municipality deduced from the town name: 佐賀県有田町 is the only match in Japan |
| 追分町6丁目18-23 | ACCEPTED: 愛知県大府市追分町6丁目18番23号 | municipality deduced from the town name: 愛知県大府市 is the only match in Japan |
| 下立売通黒門西入橋西二丁目648 | ACCEPTED: 京都府京都市中京区下立売通黒門西入橋西町2丁目648番地 | resolved 11 candidate municipalities to 京都府京都市中京区 by town '橋西町' |

**as typed: row carries a municipality code that no longer exists** (12)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 静岡県浜松市中区小豆餅2-9-13 | ACCEPTED: 静岡県浜松市中央区小豆餅2丁目9番13号 | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 浜松市中区上島1-8-53オンリーワン | ACCEPTED: 静岡県浜松市中央区上島1丁目8番53号 オンリーワン | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市東区植松町88-10マンション植松101号室 | ACCEPTED: 静岡県浜松市中央区植松町88番10号 マンション植松 101号室 | 浜松市東区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市浜名区横須賀63－5 | ACCEPTED: 静岡県浜松市浜名区横須賀63番5号 | Municipality and town verified against official registries. |
| 静岡県浜松市中区高丘東4丁目5-4Sコープ　S-1号室 | ACCEPTED: 静岡県浜松市中央区高丘東4丁目5番4号 Sコープ S 1号室 | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市西区村櫛町4218番地の1 | ACCEPTED: 静岡県浜松市中央区村櫛町4218番地の1 | 浜松市西区 no longer exists; its area is now part of 静岡県浜松市中央区 |

**with the prefecture and municipality columns: not scored: the typed address and the row's columns name different municipalities** (118)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 大阪府大阪市東住吉区南田辺二丁目12番7号 | ACCEPTED: 大阪府大阪市東住吉区南田辺2丁目12番7号 | Municipality, town and 丁目 verified against official registries. |
| 群馬県みどり市笠懸町西鹿田182番地1 | ACCEPTED: 群馬県みどり市笠懸町西鹿田182番地の1 | Municipality and town verified against official registries. |
| 北海道上川町帯広市西22条南3丁目33-1 | ACCEPTED: 北海道帯広市西二十二条南3丁目33番1号 | two municipalities are written; read the second, 帯広市, where the town is registered |
| 長崎県東彼杵郡川棚町新谷郷1700-2グループホーム　サンホーム新谷 | ACCEPTED: 長崎県東彼杵郡川棚町新谷郷1700番2号 グループホーム サンホーム新谷 | Municipality and town verified against official registries. |
| 福岡県小郡市大崎７３８－１ | ACCEPTED: 福岡県小郡市大崎738番1号 | Municipality and town verified against official registries. |
| 茨城県水戸市平須町１８２２番地の２２７　原口アパート２号 | ACCEPTED: 茨城県水戸市平須町1822番地の227 原口アパート 2号 | Municipality and town verified against official registries. |

**with the prefecture and municipality columns: rejected: UNSUPPORTED** (95)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 富山県高岡氏二上町1144-2 | UNSUPPORTED: 富山県高岡氏二上町1144-2 | no municipality found: the text is returned as written, not interpreted |
| 青森県森県下北郡東通村大字白糠字家ノ上43-4 | UNSUPPORTED: 青森県森県下北郡東通村大字白糠字家ノ上43-4 | no municipality found: the text is returned as written, not interpreted |
| 徳島県徳s摩市国府町井戸字左ケ池39番地1 | UNSUPPORTED: 徳島県徳s摩市国府町井戸字左ケ池39番地1 | no municipality found: the text is returned as written, not interpreted |
| 長野県郡野沢温泉村大字豊郷4399番地 | UNSUPPORTED: 長野県郡野沢温泉村大字豊郷4399番地 | Administrative entity could not be resolved to a local government code. |
| 宮崎県北諸県三股町大字樺山4836番26 | UNSUPPORTED: 宮崎県北諸県三股町大字樺山4836番26 | no municipality found: the text is returned as written, not interpreted |
| 富山県富山市水橋辻 | UNSUPPORTED: 富山県富山市水橋辻 | town '水橋辻' is not registered in 富山市 |

**with the prefecture and municipality columns: rejected: MALFORMED** (26)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 知県名古屋市西区幅下2丁目11－14松原ビル2階 | MALFORMED: 知県名古屋市西区幅下2丁目11-14松原ビル2階 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 兵庫県神戸市東灘区御影中町14-10-208石川ビル２０８ | MALFORMED: 兵庫県神戸市東灘区御影中町14丁目10番208号 石川ビル 208 | 御影中町 has only 1–8丁目; 14丁目 does not exist |
| 岡山県北区津島福居12-13-17 | MALFORMED: 岡山県岡山市北区津島福居12丁目13番17号 | 津島福居 has only 1–2丁目; 12丁目 does not exist |
| 胃姫健大洲市長浜甲176番地 | MALFORMED: 胃姫健大洲市長浜甲176番地 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 大阪府富田林市甲田23丁目10番2号 | MALFORMED: 大阪府富田林市甲田23丁目10番2号 | 甲田 has only 1–6丁目; 23丁目 does not exist |
| 茨木県古河市長谷町22－22 | MALFORMED: 茨木県古河市長谷町22-22 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |

**with the prefecture and municipality columns: ambiguous, truth listed** (23)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 長野県大町３１３０番地 | AMBIGUOUS: 長野県大町3130番地 | Ambiguous administrative jurisdiction matches 2 candidates. |
| 山梨県大久保1357 | AMBIGUOUS: 山梨県大久保1357 | the municipality is ambiguous: the text is returned as written, not interpreted |
| 山口県新地３丁目５－１ | AMBIGUOUS: 山口県新地3丁目5-1 | the municipality is ambiguous: the text is returned as written, not interpreted |
| 茨城県荒川沖5-44CBI101 | AMBIGUOUS: 茨城県荒川沖5-44CBI101 | the municipality is ambiguous: the text is returned as written, not interpreted |
| 愛知県名古屋市西新12-9 | AMBIGUOUS: 愛知県名古屋市西新12-9 | town '西新' is not registered in any ward of 名古屋市 |
| 大阪府寿町4-5-20 | AMBIGUOUS: 大阪府寿町4-5-20 | the municipality is ambiguous: the text is returned as written, not interpreted |

**with the prefecture and municipality columns: row carries a municipality code that no longer exists** (15)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 静岡県浜松市中区佐藤１－２６－３２ | ACCEPTED: 静岡県浜松市中央区佐藤1丁目26番32号 | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市中区小豆餅2-9-13 | ACCEPTED: 静岡県浜松市中央区小豆餅2丁目9番13号 | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市中区上島1-8-53オンリーワン | ACCEPTED: 静岡県浜松市中央区上島1丁目8番53号 オンリーワン | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市東区植松町88-10マンション植松101号室 | ACCEPTED: 静岡県浜松市中央区植松町88番10号 マンション植松 101号室 | 浜松市東区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市天竜区横山町746-8 | ACCEPTED: 静岡県浜松市天竜区横山町746番8号 | Municipality and town verified against official registries. |
| 静岡県浜松市浜名区横須賀63－5 | ACCEPTED: 静岡県浜松市浜名区横須賀63番5号 | Municipality and town verified against official registries. |

**with the prefecture and municipality columns: wrong** (4)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 大阪府堺市緑ヶ丘南町4-2-23グリーンヒルズ2D | ACCEPTED: 大阪府堺市堺区緑ヶ丘南町四丁2番23号 グリーンヒルズ2D | resolved 7 candidate municipalities to 大阪府堺市堺区 by town '緑ヶ丘南町四丁' |
| 茨城県駒場3丁目7－15 | ACCEPTED: 茨城県取手市駒場3丁目7番15号 | resolved 44 candidate municipalities to 茨城県取手市 by town '駒場' |
| 熊本県熊本市流通団地2-20-1センコービル2階 | ACCEPTED: 熊本県熊本市南区流通団地2丁目20番1号 センコービル 2階 | resolved 5 candidate municipalities to 熊本県熊本市南区 by town '流通団地' |
| 兵庫県赤穂市上郡町竹万381-5シャイン上郡 | ACCEPTED: 兵庫県赤穂郡上郡町竹万381番5号 シャイン上郡 | two municipalities are written; read the second, 上郡町, where the town is registered |

**with the prefecture and municipality columns: ambiguous, truth not listed** (2)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 静岡県静岡市岡部町岡部437番地の3 | AMBIGUOUS: 静岡県静岡市岡部町岡部437番地の3 | town '岡部町岡部' is not registered in any ward of 静岡市 |
| 大阪府大阪市六万寺町1丁目14番20号 | AMBIGUOUS: 大阪府大阪市六万寺町1丁目14番20号 | town '六万寺町' is not registered in any ward of 大阪市 |

**town: town not in the registry** (1,036)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 京都府城陽市中芦原55番地 | ACCEPTED: 京都府城陽市中芦原55番地 | town '中芦原' is not registered in 城陽市 |
| 神奈川県横浜市南区六ッ川２丁目123－13サウスMYビル２階 | ACCEPTED: 神奈川県横浜市南区六ッ川2丁目123番13号 サウスMYビル 2階 | town '六ッ川' is not registered in 横浜市南区 |
| 鳥取県鳥取市正連寺51番地1 | ACCEPTED: 鳥取県鳥取市正連寺51番地の1 | town '正連寺' is not registered in 鳥取市 |
| 愛知県　豊田市九久平百々11-17 | ACCEPTED: 愛知県豊田市九久平百々11番17号 | town '九久平百々' is not registered in 豊田市 |
| 福岡県久留米市三瀦町高三潴147-1 | ACCEPTED: 福岡県久留米市三瀦町高三潴147番1号 | town '三瀦町高三潴' is not registered in 久留米市 |
| 釧路郡釧路町陸2丁目1番地１０ | ACCEPTED: 北海道釧路郡釧路町陸2丁目1番地の10 | town '陸' is not registered in 釧路町 |

**town: no town written** (558)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 長野県諏訪郡下諏訪町6174-1 | ACCEPTED: 長野県諏訪郡下諏訪町6174番1号 | Local government entity verified against official statutory registry. |
| 長野県上伊那郡南箕輪村8987-1漆戸テナント1階1号室 | ACCEPTED: 長野県上伊那郡南箕輪村8987番1号 漆戸テナント 1階 1号室 | Local government entity verified against official statutory registry. |
| 長野県上伊那郡宮田村4804-1 | ACCEPTED: 長野県上伊那郡宮田村4804番1号 | Local government entity verified against official statutory registry. |
| 大分県日田市３丁目1479-3 | ACCEPTED: 大分県日田市3丁目1479番3号 | Local government entity verified against official statutory registry. |
| 長野県諏訪郡原村13220番地1 | ACCEPTED: 長野県諏訪郡原村13220番地の1 | Local government entity verified against official statutory registry. |
| 香川県綾歌郡宇多津町１７０番地１ | ACCEPTED: 香川県綾歌郡宇多津町170番地の1 | Local government entity verified against official statutory registry. |

`not decidable` rows are shown for completeness; nothing in the text says where the number ends.

**building: not decidable: the publisher glued a number to the house number** (631)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 神奈川県相模原市南区東林間2-21-6201 | ACCEPTED: 神奈川県相模原市南区東林間2丁目21番6201号 | without the building: 神奈川県相模原市南区東林間2丁目21番6号 |
| 東京都大田区大森西４丁目３－５３０７ | ACCEPTED: 東京都大田区大森西4丁目3番5307号 | without the building: 東京都大田区大森西4丁目3番5号 |
| 東京都練馬区石神井町６－３２－１２２０１ | ACCEPTED: 東京都練馬区石神井町6丁目32番12201号 | without the building: 東京都練馬区石神井町6丁目32番12号 |
| 兵庫県尼崎市中在家町３-３７０１０２ | ACCEPTED: 兵庫県尼崎市中在家町3丁目370102番 | without the building: 兵庫県尼崎市中在家町3丁目370番 |
| 兵庫県西宮市大屋町5-17-103103 | ACCEPTED: 兵庫県西宮市大屋町5-17-103103 | without the building: 兵庫県西宮市大屋町5-17-103 |
| 東京都町田市成瀬が丘2-22-8101 | ACCEPTED: 東京都町田市成瀬が丘2丁目22番8101号 | without the building: 東京都町田市成瀬が丘2丁目22番8号 |

**building: address changes when the building is attached** (104)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 兵庫県丹波市青垣町東芦田1303番地1303 | ACCEPTED: 兵庫県丹波市青垣町東芦田1303番地の1303 | without the building: 兵庫県丹波市青垣町東芦田1303番地 |
| 大阪府寝屋川市萱島南町8丁目23番201号 | ACCEPTED: 大阪府寝屋川市萱島南町8丁目23番201号 | without the building: 大阪府寝屋川市萱島南町8丁目23番 |
| 富山県高岡市二塚1316番地1316番地 | ACCEPTED: 富山県高岡市二塚1316番地の1316 番地 | without the building: 富山県高岡市二塚1316番地 |
| 福岡県福岡市中央区長浜2丁目5-22Fビル3階 | ACCEPTED: 福岡県福岡市中央区長浜2丁目5番2号 2Fビル3階 | without the building: 福岡県福岡市中央区長浜2丁目5番22号 |
| 京都府城陽市寺田垣内後29番地17 | ACCEPTED: 京都府城陽市寺田垣内後29番地の17 | without the building: 京都府城陽市寺田垣内後29番地 |
| 福島県福島市永井川字檀ノ腰2-2Fフェアリー105 | ACCEPTED: 福島県福島市永井川字檀ノ腰2番地 フェアリー 2F 105 | without the building: 福島県福島市永井川字檀ノ腰2番地の2 |

**location: more than 20 km from the published point** (901)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 埼玉県春日部市浜川戸1-5-10きらら春日部 | ACCEPTED: 埼玉県春日部市浜川戸1丁目5番10号 きらら春日部 | 136 km; published 36.204824,138.252924 |
| 宮崎県宮崎市祇園2丁目23-2 | ACCEPTED: 宮崎県宮崎市祇園2丁目23番2号 | 296 km; published 34.442372,132.466396 |
| 福井県越前市本多1丁目8-12 | ACCEPTED: 福井県越前市本多1丁目8番12号 | 300 km; published 35.705519,139.483367 |
| 兵庫県姫路市西中島５３番 | ACCEPTED: 兵庫県姫路市西中島53番 | 73 km; published 34.725524,135.499268 |
| 山梨県甲府市城東5丁目10-11 | ACCEPTED: 山梨県甲府市城東5丁目10番11号 | 190 km; published 36.377777,140.499107 |
| 埼玉県上尾市東町1-8-7 | ACCEPTED: 埼玉県上尾市東町1丁目8番7号 | 32 km; published 35.689836,139.523223 |

**same office: spellings get different keys** (first examples)

| Spelling A | Spelling B | Key A | Key B |
| :--- | :--- | :--- | :--- |
| 北海道札幌市東区2条4丁目8-20社会医療法人社団三草会クラーク病院内 | 北海道札幌市東区本町2条4丁目8－20クラーク病院2階 | 011037|2条|4|8|20 | 011037|本町2条|4|8|20 |
| 北海道旭川市末広5条7丁目1番1号 | 北海道旭川市末広５条７丁目１番１号 | 012041|末広5条|7|1|1 | 012041|末広5条|7|1|1 |
| 北海道網走市字潮見網走市字潮見153番地1 | 北海道網走市字潮見１５３番地1 | 012114|潮見/網走市字潮見||153|1 | 012114|潮見||153|1 |
| 北海道旭川市豊岡13条1丁目1番11号 | 旭川市豊岡13条1丁目1番17号 | 012041|豊岡13条|1|1|11 | 012041|豊岡13条|1|1|17 |
| 北海道苫小牧市桜木町２丁目２５番１号 | 苫小牧桜木町２丁目25番1号 | 012131|桜木町|2|25|1 | 012131|苫小牧桜木町|2|25|1 |
| 北海道釧路郡釧路町睦2丁目1番地10 | 北海道釧路郡釧路町陸2丁目1番地１０ | 016616|睦|2|1|10 | 016616|陸|2|1|10 |

