# Real data: long-term-care office addresses (Ministry of Health, Labour and Welfare)

Source: 介護サービス情報公表システム オープンデータ (data as of 2026年６月末時点, CC BY). Rows used: every office row with an address: **223,161**. Processed in 41 s on 4 processes.

Every row is a real office, so the right municipality outcome is always `correct`.

## The address exactly as typed (often without prefecture or municipality)

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| correct | 218,425 | 97.88% |
| ambiguous, truth listed | 4,091 | 1.83% |
| rejected: MALFORMED | 294 | 0.13% |
| not scored: the typed address and the row's columns name different municipalities | 128 | 0.06% |
| rejected: UNSUPPORTED | 127 | 0.06% |
| ambiguous, truth not listed | 59 | 0.03% |
| wrong | 13 | 0.01% |
| city only: the ward was not resolved | 12 | 0.01% |
| row carries a municipality code that no longer exists | 12 | 0.01% |
| **all** | 223,161 |  |

## With the row's prefecture and municipality columns put in front where the text lacks them

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| correct | 222,876 | 99.87% |
| not scored: the typed address and the row's columns name different municipalities | 120 | 0.05% |
| rejected: UNSUPPORTED | 95 | 0.04% |
| rejected: MALFORMED | 26 | 0.01% |
| row carries a municipality code that no longer exists | 15 | 0.01% |
| ambiguous, truth listed | 13 | 0.01% |
| city only: the ward was not resolved | 12 | 0.01% |
| wrong | 4 | 0.00% |
| **all** | 223,161 |  |

## Town (of the addresses with the right municipality)

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| town verified | 221,294 | 99.29% |
| town not in the registry | 1,018 | 0.46% |
| no town written | 564 | 0.25% |
| **all** | 222,876 |  |

## Building, floor and room against the 方書 column

Rows whose typed address ends with the text of the 方書 column. The address is resolved with and without that text; the address part must not change.

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| same address, building separated | 47,682 | 95.76% |
| not scored: the 方書 column holds only part of the building text | 1,285 | 2.58% |
| not decidable: the publisher glued a number to the house number | 632 | 1.27% |
| address changes when the building is attached | 103 | 0.21% |
| not scored: the 方書 column holds the house number too | 66 | 0.13% |
| same address, building text dropped | 25 | 0.05% |
| **all** | 49,793 |  |

## The same office listed several times with different spellings

Offices (by 事業所番号) whose rows carry two or more different address strings. Where the strings carry the same numbers, they should get the same house-level match key.

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| all spellings share one key | 9,807 | 84.27% |
| not scored: the spellings carry different numbers (a move, or a typo in the data) | 1,316 | 11.31% |
| spellings get different keys | 355 | 3.05% |
| a spelling could not be keyed | 160 | 1.37% |
| **all** | 11,638 |  |

Of the offices whose spellings carry the same numbers, **95.01%** get one key (9,807 of 10,322).

## Distance from JADEN's offline point to the published coordinates

The published coordinates come from the publishing system's own geocoding, so this is agreement between two systems, not error against a survey.

| JADEN point level | Addresses | Median distance | Within 1 km | Over 20 km |
| :--- | ---: | ---: | ---: | ---: |
| town | 124,201 | 533 m | 73.9% | 0.33% |
| chome | 96,323 | 157 m | 98.5% | 0.51% |

## Precision reached

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| house | 190,249 | 85.36% |
| unit | 17,278 | 7.75% |
| block | 15,128 | 6.79% |
| chome | 155 | 0.07% |
| town | 65 | 0.03% |
| municipality | 1 | 0.00% |
| **all** | 222,876 |  |

## Examples of what is not `correct`

**as typed: ambiguous, truth listed** (4,091)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 新在家125-11リブハウス・アズ1Ｆ | AMBIGUOUS: 新在家125番11号 リブハウス・アズ 1F | Omitted prefecture matches 6 statutory municipalities. |
| 小野町5-89-10 | AMBIGUOUS: 小野町5丁目89番10号 | '小野町' is a municipality and also a town name in 16 other place(s) |
| 船戸1-19-16 | AMBIGUOUS: 船戸1丁目19番16号 | Omitted prefecture matches 8 statutory municipalities. |
| 大字津留字六本松1970-7 | AMBIGUOUS: 大字津留字六本松1970番地の7 | Omitted prefecture matches 8 statutory municipalities. |
| 玉沢９０番地 | AMBIGUOUS: 玉沢90番地 | Omitted prefecture matches 2 statutory municipalities. |
| 若宮二丁目41番22号 | AMBIGUOUS: 若宮2丁目41番22号 | Omitted prefecture matches 47 statutory municipalities. |

**as typed: rejected: MALFORMED** (294)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 下安原町東1457番地1第2やすはら苑 | MALFORMED: 下安原町東1457番地1第2やすはら苑 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 壱丁目東３６－３エクラシア上尾西 | MALFORMED: 壱丁目東36-3エクラシア上尾西 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 4-4-25やさしえ東辻井 | MALFORMED: 4-4-25やさしえ東辻井 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 605WORKPLACE春田 | MALFORMED: 605WORKPLACE春田 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 中泉御殿703 | MALFORMED: 中泉御殿703 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |
| 奥海印寺多貝垣外17-1 | MALFORMED: 奥海印寺多貝垣外17-1 | Input rejected: no recognized Japanese administrative jurisdiction or structure. |

**as typed: not scored: the typed address and the row's columns name different municipalities** (128)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 大阪市東住吉区南田辺二丁目12番7号 | ACCEPTED: 大阪府大阪市東住吉区南田辺2丁目12番7号 | Municipality, town and 丁目 verified against official registries. |
| 群馬県みどり市笠懸町西鹿田182番地1 | ACCEPTED: 群馬県みどり市笠懸町西鹿田182番地の1 | Municipality and town verified against official registries. |
| 帯広市西22条南3丁目33-1 | ACCEPTED: 北海道帯広市西二十二条南3丁目33番1号 | Municipality, town and 丁目 verified against official registries. |
| 長崎県東彼杵郡川棚町新谷郷1700-2グループホーム　サンホーム新谷 | ACCEPTED: 長崎県東彼杵郡川棚町新谷郷1700番2号 グループホーム サンホーム新谷 | Municipality and town verified against official registries. |
| 福岡県小郡市大崎７３８－１ | ACCEPTED: 福岡県小郡市大崎738番1号 | Municipality and town verified against official registries. |
| 高浜町6-1　1階 | ACCEPTED: 福井県大飯郡高浜町6番1号 1階 | Local government entity verified against official statutory registry. |

**as typed: rejected: UNSUPPORTED** (127)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 奈良町32-42階 | UNSUPPORTED: 町32番4号 2階 | Administrative entity could not be resolved to a local government code. |
| 富山県高岡氏二上町1144-2 | UNSUPPORTED: 富山県高岡氏二上町1144番2号 | Administrative entity could not be resolved to a local government code. |
| 長野1499番地 | UNSUPPORTED: 長野県1499番地 | Administrative entity could not be resolved to a local government code. |
| 徳島県徳s摩市国府町井戸字左ケ池39番地1 | UNSUPPORTED: 徳島県徳s摩市国府町井戸字左ケ池39番地の1 | Administrative entity could not be resolved to a local government code. |
| 長野県郡野沢温泉村大字豊郷4399番地 | UNSUPPORTED: 長野県郡野沢温泉村大字豊郷4399番地 | Administrative entity could not be resolved to a local government code. |
| 宮崎県北諸県三股町大字樺山4836番26 | UNSUPPORTED: 宮崎県北諸県三股町大字樺山4836番地の26 | Administrative entity could not be resolved to a local government code. |

**as typed: ambiguous, truth not listed** (59)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 佐藤１－２６－３２ | AMBIGUOUS: 佐藤1丁目26番32号 | Omitted prefecture matches 2 statutory municipalities. |
| 吉野3丁目5番8号 | AMBIGUOUS: 吉野3丁目5番8号 | Omitted prefecture matches 15 statutory municipalities. |
| 甲5229番地13 | AMBIGUOUS: 甲5229番地の13 | Omitted prefecture matches 8 statutory municipalities. |
| 川西町4668-3 | AMBIGUOUS: 川西町4668番3号 | Omitted prefecture matches 2 statutory municipalities. |
| 一宮町1566－1 | AMBIGUOUS: 一宮町1566番1号 | '一宮町' is a municipality and also a town name in 4 other place(s) |
| 南山３丁目２３番地２７ | AMBIGUOUS: 南山3丁目23番地の27 | Omitted prefecture matches 7 statutory municipalities. |

**as typed: wrong** (13)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 久住町６４８２番地 | ACCEPTED: 鹿児島県薩摩川内市久住町6482番地 | municipality deduced from the town name: 鹿児島県薩摩川内市 is the only match in Japan |
| 御車道通清和院口上る東側梶井町457-1 | ACCEPTED: 京都府京都市上京区御車道通清和院口上る東側梶井町457番地の1 | resolved 11 candidate municipalities to 京都府京都市上京区 by town '梶井町' |
| 大阪府堺市緑ヶ丘南町4-2-23グリーンヒルズ2D | ACCEPTED: 大阪府堺市堺区緑ヶ丘南町四丁2番23号 グリーンヒルズ2D | resolved 7 candidate municipalities to 大阪府堺市堺区 by town '緑ヶ丘南町四丁' |
| 舞原344-2あすなろ熊本壱番館 | ACCEPTED: 佐賀県西松浦郡有田町舞原344番2号 あすなろ熊本壱番館 | municipality deduced from the town name: 佐賀県有田町 is the only match in Japan |
| 追分町6丁目18-23 | ACCEPTED: 愛知県大府市追分町6丁目18番23号 | resolved 9 candidate municipalities to 愛知県大府市 by town '追分町' |
| 下立売通黒門西入橋西二丁目648 | ACCEPTED: 京都府京都市中京区下立売通黒門西入橋西町2丁目648番地 | resolved 11 candidate municipalities to 京都府京都市中京区 by town '橋西町' |

**as typed: city only: the ward was not resolved** (12)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 北海道札幌市本町１条４丁目１－１８ヤマモトビル１階 | ACCEPTED: 北海道札幌市本町1条4丁目1番18号 ヤマモトビル 1階 | town '本町1条' is not registered in any ward of 札幌市 |
| 愛知県名古屋市西新12-9 | ACCEPTED: 愛知県名古屋市西新12番9号 | town '西新' is not registered in any ward of 名古屋市 |
| 広島市県広島市安佐南区伴東7丁目55番9号villa大原駅前101号 | ACCEPTED: 広島県広島市県広島市安佐南区伴東7丁目55番9号 villa大原駅前 101号 | town '県広島市安佐南区伴東' is not registered in any ward of 広島市 |
| 岡山県岡山市南福田95-2 | ACCEPTED: 岡山県岡山市南福田95番2号 | town '南福田' is not registered in any ward of 岡山市 |
| 静岡県浜松市区中央曳馬3－39－22 | ACCEPTED: 静岡県浜松市区中央曳馬3丁目39番22号 | town '区中央曳馬' is not registered in any ward of 浜松市 |
| 静岡県浜松市名北区中瀬6569-1 | ACCEPTED: 静岡県浜松市名北区中瀬6569番1号 | town '名北区中瀬' is not registered in any ward of 浜松市 |

**as typed: row carries a municipality code that no longer exists** (12)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 静岡県浜松市中区小豆餅2-9-13 | ACCEPTED: 静岡県浜松市中央区小豆餅2丁目9番13号 | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 浜松市中区上島1-8-53オンリーワン | ACCEPTED: 静岡県浜松市中央区上島1丁目8番53号 オンリーワン | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市東区植松町88-10マンション植松101号室 | ACCEPTED: 静岡県浜松市中央区植松町88番10号 マンション植松 101号室 | 浜松市東区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市浜名区横須賀63－5 | ACCEPTED: 静岡県浜松市浜名区横須賀63番5号 | Municipality and town verified against official registries. |
| 静岡県浜松市中区高丘東4丁目5-4Sコープ　S-1号室 | ACCEPTED: 静岡県浜松市中央区高丘東4丁目5番4号 Sコープ S 1号室 | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市西区村櫛町4218番地の1 | ACCEPTED: 静岡県浜松市中央区村櫛町4218番地の1 | 浜松市西区 no longer exists; its area is now part of 静岡県浜松市中央区 |

**with the prefecture and municipality columns: not scored: the typed address and the row's columns name different municipalities** (120)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 大阪府大阪市東住吉区南田辺二丁目12番7号 | ACCEPTED: 大阪府大阪市東住吉区南田辺2丁目12番7号 | Municipality, town and 丁目 verified against official registries. |
| 群馬県みどり市笠懸町西鹿田182番地1 | ACCEPTED: 群馬県みどり市笠懸町西鹿田182番地の1 | Municipality and town verified against official registries. |
| 北海道上川町帯広市西22条南3丁目33-1 | ACCEPTED: 北海道帯広市西二十二条南3丁目33番1号 | two municipalities are written; read the second, 帯広市, where the town is registered |
| 長崎県東彼杵郡川棚町新谷郷1700-2グループホーム　サンホーム新谷 | ACCEPTED: 長崎県東彼杵郡川棚町新谷郷1700番2号 グループホーム サンホーム新谷 | Municipality and town verified against official registries. |
| 福岡県小郡市大崎７３８－１ | ACCEPTED: 福岡県小郡市大崎738番1号 | Municipality and town verified against official registries. |
| 静岡県静岡市岡部町岡部437番地の3 | ACCEPTED: 静岡県静岡市岡部町岡部437番地の3 | town '岡部町岡部' is not registered in any ward of 静岡市 |

**with the prefecture and municipality columns: rejected: UNSUPPORTED** (95)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 富山県高岡氏二上町1144-2 | UNSUPPORTED: 富山県高岡氏二上町1144番2号 | Administrative entity could not be resolved to a local government code. |
| 青森県森県下北郡東通村大字白糠字家ノ上43-4 | UNSUPPORTED: 青森県森県下北郡東通村大字白糠字家ノ上43番地の4 | Administrative entity could not be resolved to a local government code. |
| 徳島県徳s摩市国府町井戸字左ケ池39番地1 | UNSUPPORTED: 徳島県徳s摩市国府町井戸字左ケ池39番地の1 | Administrative entity could not be resolved to a local government code. |
| 長野県郡野沢温泉村大字豊郷4399番地 | UNSUPPORTED: 長野県郡野沢温泉村大字豊郷4399番地 | Administrative entity could not be resolved to a local government code. |
| 宮崎県北諸県三股町大字樺山4836番26 | UNSUPPORTED: 宮崎県北諸県三股町大字樺山4836番地の26 | Administrative entity could not be resolved to a local government code. |
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

**with the prefecture and municipality columns: row carries a municipality code that no longer exists** (15)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 静岡県浜松市中区佐藤１－２６－３２ | ACCEPTED: 静岡県浜松市中央区佐藤1丁目26番32号 | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市中区小豆餅2-9-13 | ACCEPTED: 静岡県浜松市中央区小豆餅2丁目9番13号 | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市中区上島1-8-53オンリーワン | ACCEPTED: 静岡県浜松市中央区上島1丁目8番53号 オンリーワン | 浜松市中区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市東区植松町88-10マンション植松101号室 | ACCEPTED: 静岡県浜松市中央区植松町88番10号 マンション植松 101号室 | 浜松市東区 no longer exists; its area is now part of 静岡県浜松市中央区 |
| 静岡県浜松市天竜区横山町746-8 | ACCEPTED: 静岡県浜松市天竜区横山町746番8号 | Municipality and town verified against official registries. |
| 静岡県浜松市浜名区横須賀63－5 | ACCEPTED: 静岡県浜松市浜名区横須賀63番5号 | Municipality and town verified against official registries. |

**with the prefecture and municipality columns: ambiguous, truth listed** (13)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 長野県大町３１３０番地 | AMBIGUOUS: 長野県大町3130番地 | Ambiguous administrative jurisdiction matches 2 candidates. |
| 山梨県大久保1357 | AMBIGUOUS: 山梨県大久保1357番 | Ambiguous administrative jurisdiction matches 4 candidates. |
| 山口県新地３丁目５－１ | AMBIGUOUS: 山口県新地3丁目5番1号 | Ambiguous administrative jurisdiction matches 2 candidates. |
| 茨城県荒川沖5-44CBI101 | AMBIGUOUS: 茨城県荒川沖5番44号 CBI 101 | Ambiguous administrative jurisdiction matches 2 candidates. |
| 大阪府寿町4-5-20 | AMBIGUOUS: 大阪府寿町4丁目5番20号 | Ambiguous administrative jurisdiction matches 6 candidates. |
| 宮崎県桜ヶ丘二丁目506-16 | AMBIGUOUS: 宮崎県桜ヶ丘2丁目506番16号 | Ambiguous administrative jurisdiction matches 2 candidates. |

**with the prefecture and municipality columns: city only: the ward was not resolved** (12)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 北海道札幌市本町１条４丁目１－１８ヤマモトビル１階 | ACCEPTED: 北海道札幌市本町1条4丁目1番18号 ヤマモトビル 1階 | town '本町1条' is not registered in any ward of 札幌市 |
| 愛知県名古屋市西新12-9 | ACCEPTED: 愛知県名古屋市西新12番9号 | town '西新' is not registered in any ward of 名古屋市 |
| 広島市県広島市安佐南区伴東7丁目55番9号villa大原駅前101号 | ACCEPTED: 広島県広島市県広島市安佐南区伴東7丁目55番9号 villa大原駅前 101号 | town '県広島市安佐南区伴東' is not registered in any ward of 広島市 |
| 岡山県岡山市南福田95-2 | ACCEPTED: 岡山県岡山市南福田95番2号 | town '南福田' is not registered in any ward of 岡山市 |
| 静岡県浜松市区中央曳馬3－39－22 | ACCEPTED: 静岡県浜松市区中央曳馬3丁目39番22号 | town '区中央曳馬' is not registered in any ward of 浜松市 |
| 静岡県浜松市名北区中瀬6569-1 | ACCEPTED: 静岡県浜松市名北区中瀬6569番1号 | town '名北区中瀬' is not registered in any ward of 浜松市 |

**with the prefecture and municipality columns: wrong** (4)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 大阪府堺市緑ヶ丘南町4-2-23グリーンヒルズ2D | ACCEPTED: 大阪府堺市堺区緑ヶ丘南町四丁2番23号 グリーンヒルズ2D | resolved 7 candidate municipalities to 大阪府堺市堺区 by town '緑ヶ丘南町四丁' |
| 茨城県駒場3丁目7－15 | ACCEPTED: 茨城県取手市駒場3丁目7番15号 | resolved 44 candidate municipalities to 茨城県取手市 by town '駒場' |
| 熊本県熊本市流通団地2-20-1センコービル2階 | ACCEPTED: 熊本県熊本市南区流通団地2丁目20番1号 センコービル 2階 | resolved 5 candidate municipalities to 熊本県熊本市南区 by town '流通団地' |
| 兵庫県赤穂市上郡町竹万381-5シャイン上郡 | ACCEPTED: 兵庫県赤穂郡上郡町竹万381番5号 シャイン上郡 | two municipalities are written; read the second, 上郡町, where the town is registered |

**town: town not in the registry** (1,018)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 京都府城陽市中芦原55番地 | ACCEPTED: 京都府城陽市中芦原55番地 | town '中芦原' is not registered in 城陽市 |
| 神奈川県横浜市南区六ッ川２丁目123－13サウスMYビル２階 | ACCEPTED: 神奈川県横浜市南区六ッ川2丁目123番13号 サウスMYビル 2階 | town '六ッ川' is not registered in 横浜市南区 |
| 鳥取県鳥取市正連寺51番地1 | ACCEPTED: 鳥取県鳥取市正連寺51番地の1 | town '正連寺' is not registered in 鳥取市 |
| 愛知県　豊田市九久平百々11-17 | ACCEPTED: 愛知県豊田市九久平百々11番17号 | town '九久平百々' is not registered in 豊田市 |
| 福岡県久留米市三瀦町高三潴147-1 | ACCEPTED: 福岡県久留米市三瀦町高三潴147番1号 | town '三瀦町高三潴' is not registered in 久留米市 |
| 釧路郡釧路町陸2丁目1番地１０ | ACCEPTED: 北海道釧路郡釧路町陸2丁目1番地の10 | town '陸' is not registered in 釧路町 |

**town: no town written** (564)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 長野県諏訪郡下諏訪町6174-1 | ACCEPTED: 長野県諏訪郡下諏訪町6174番1号 | Local government entity verified against official statutory registry. |
| 長野県上伊那郡南箕輪村8987-1漆戸テナント1階1号室 | ACCEPTED: 長野県上伊那郡南箕輪村8987番1号 漆戸テナント 1階 1号室 | Local government entity verified against official statutory registry. |
| 長野県上伊那郡宮田村4804-1 | ACCEPTED: 長野県上伊那郡宮田村4804番1号 | Local government entity verified against official statutory registry. |
| 大分県日田市３丁目1479-3 | ACCEPTED: 大分県日田市3丁目1479番3号 | Local government entity verified against official statutory registry. |
| 長野県諏訪郡原村13220番地1 | ACCEPTED: 長野県諏訪郡原村13220番地の1 | Local government entity verified against official statutory registry. |
| 香川県綾歌郡宇多津町１７０番地１ | ACCEPTED: 香川県綾歌郡宇多津町170番地の1 | Local government entity verified against official statutory registry. |

`not decidable` rows are shown for completeness; nothing in the text says where the number ends.

**building: not decidable: the publisher glued a number to the house number** (632)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 神奈川県相模原市南区東林間2-21-6201 | ACCEPTED: 神奈川県相模原市南区東林間2丁目21番6201号 | without the building: 神奈川県相模原市南区東林間2丁目21番6号 |
| 東京都大田区大森西４丁目３－５３０７ | ACCEPTED: 東京都大田区大森西4丁目3番5307号 | without the building: 東京都大田区大森西4丁目3番5号 |
| 東京都練馬区石神井町６－３２－１２２０１ | ACCEPTED: 東京都練馬区石神井町6丁目32番12201号 | without the building: 東京都練馬区石神井町6丁目32番12号 |
| 兵庫県尼崎市中在家町３-３７０１０２ | ACCEPTED: 兵庫県尼崎市中在家町3丁目370102番 | without the building: 兵庫県尼崎市中在家町3丁目370番 |
| 兵庫県西宮市大屋町5-17-103103 | ACCEPTED: 兵庫県西宮市大屋町5-17-103103 | without the building: 兵庫県西宮市大屋町5-17-103 |
| 東京都町田市成瀬が丘2-22-8101 | ACCEPTED: 東京都町田市成瀬が丘2丁目22番8101号 | without the building: 東京都町田市成瀬が丘2丁目22番8号 |

**building: address changes when the building is attached** (103)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 兵庫県丹波市青垣町東芦田1303番地1303 | ACCEPTED: 兵庫県丹波市青垣町東芦田1303番地の1303 | without the building: 兵庫県丹波市青垣町東芦田1303番地 |
| 大阪府寝屋川市萱島南町8丁目23番201号 | ACCEPTED: 大阪府寝屋川市萱島南町8丁目23番201号 | without the building: 大阪府寝屋川市萱島南町8丁目23番 |
| 富山県高岡市二塚1316番地1316番地 | ACCEPTED: 富山県高岡市二塚1316番地の1316 番地 | without the building: 富山県高岡市二塚1316番地 |
| 福岡県福岡市中央区長浜2丁目5-22Fビル3階 | ACCEPTED: 福岡県福岡市中央区長浜2丁目5番2号 ビル3階 2F | without the building: 福岡県福岡市中央区長浜2丁目5番22号 |
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
| 北海道札幌市北区北２９条西４丁目２番１－１５８ファミール札幌 | 札幌市北区北29条西４丁目、2-1-158 | 011029|北29条西|4|1|158 | 011029|北29条西|4|2|1 |
| 北海道旭川市末広5条7丁目1番1号 | 北海道旭川市末広５条７丁目１番１号 | 012041|末広5条|7|1|1 | 012041|末広5条|7|1|1 |
| 北海道網走市字潮見網走市字潮見153番地1 | 北海道網走市字潮見１５３番地1 | 012114|潮見/網走市字潮見||153|1 | 012114|潮見||153|1 |
| 北海道旭川市豊岡13条1丁目1番11号 | 旭川市豊岡13条1丁目1番17号 | 012041|豊岡13条|1|1|11 | 012041|豊岡13条|1|1|17 |
| 北海道苫小牧市桜木町２丁目２５番１号 | 苫小牧桜木町２丁目25番1号 | 012131|桜木町|2|25|1 | 012131|苫小牧桜木町|2|25|1 |

