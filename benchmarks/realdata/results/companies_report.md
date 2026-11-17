# Real data: registered company addresses (National Tax Agency)

Source: 国税庁法人番号公表サイト, full download `00_zenkoku_all_20261030.csv` (data as of 2026-10-30). Rows used: active corporations with a domestic address: **5,049,462**. Processed in 1,215 s (12,469 addresses/s on 4 processes; each row is resolved three ways).

Every row is a real registered address, so the right outcome is always `correct`.

## Full address (prefecture + municipality + registered text)

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| correct | 5,048,534 | 99.98% |
| rejected: UNSUPPORTED | 456 | 0.01% |
| row carries a municipality code that no longer exists | 207 | 0.00% |
| rejected: MALFORMED | 192 | 0.00% |
| correct (ward found; the row has only the city code) | 67 | 0.00% |
| wrong | 6 | 0.00% |
| **all** | 5,049,462 |  |

## Without the prefecture

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| correct | 5,036,231 | 99.74% |
| ambiguous, truth listed | 12,284 | 0.24% |
| rejected: UNSUPPORTED | 480 | 0.01% |
| row carries a municipality code that no longer exists | 182 | 0.00% |
| rejected: MALFORMED | 178 | 0.00% |
| correct (ward found; the row has only the city code) | 67 | 0.00% |
| wrong | 40 | 0.00% |
| **all** | 5,049,462 |  |

## With the registered postal code in front

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| correct | 5,045,484 | 99.98% |
| rejected: UNSUPPORTED | 449 | 0.01% |
| rejected: MALFORMED | 174 | 0.00% |
| row carries a municipality code that no longer exists | 170 | 0.00% |
| **all** | 5,046,277 |  |

## Town (of the addresses with the right municipality)

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| town verified | 4,994,100 | 98.92% |
| no town written | 32,406 | 0.64% |
| town not in the registry | 22,095 | 0.44% |
| **all** | 5,048,601 |  |

## Postal code JADEN fills in against the registered postal code

JADEN adds a postal code only when the resolved town has exactly one. The registered code is the answer; it is independent of the address text.

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| filled in, same as registered | 4,961,147 | 98.33% |
| not filled in | 48,844 | 0.97% |
| filled in the town's code; the row has the municipality-wide one | 23,023 | 0.46% |
| filled in, different from registered | 9,204 | 0.18% |
| registered code is not an area code (business code or retired) | 3,264 | 0.06% |
| **all** | 5,045,482 |  |

Where both name a town's code, **99.81%** of the codes JADEN filled in equal the registered one (4,961,147 of 4,970,351).

## Precision reached

| Outcome | Addresses | Share |
| :--- | ---: | ---: |
| house | 4,348,080 | 86.12% |
| unit | 612,330 | 12.13% |
| block | 58,339 | 1.16% |
| municipality | 24,754 | 0.49% |
| chome | 3,181 | 0.06% |
| town | 1,917 | 0.04% |
| **all** | 5,048,601 |  |

## Examples of what is not `correct`

**full: rejected: UNSUPPORTED** (456)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 愛媛県西条市氷見甲堤塘 | UNSUPPORTED: 愛媛県西条市氷見甲堤塘 | '堤塘' after the town 氷見甲 is not part of an address |
| 三重県志摩市磯部町 | UNSUPPORTED: 三重県志摩市磯部町 | town '磯部町' is not registered in 志摩市 |
| 京都府京都市下京区朱雀分木町市有地 | UNSUPPORTED: 京都府京都市下京区朱雀分木町市有地 | '市有地' after the town 朱雀分木町 is not part of an address |
| 三重県伊勢市（三重県宇治山田市岩間町外地引揚者協力今内 | UNSUPPORTED: 三重県伊勢市(三重県宇治山田市岩間町外地引揚者協力今内 | town '(三重県宇治山田市岩間町外地引揚者協力今内' is not registered in 伊勢市 |
| 北海道上川郡比布町字比布市街地 | UNSUPPORTED: 北海道上川郡比布町字比布市街地 | town '字比布市街地' is not registered in 比布町 |
| 京都府京都市下京区朱雀分木町市有地 | UNSUPPORTED: 京都府京都市下京区朱雀分木町市有地 | '市有地' after the town 朱雀分木町 is not part of an address |

**full: row carries a municipality code that no longer exists** (207)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 熊本県熊本市健軍本町４番８号 | ACCEPTED: 熊本県熊本市東区健軍本町4番8号 | resolved 5 candidate municipalities to 熊本県熊本市東区 by town '健軍本町' |
| 岡山県岡山市西崎本町７番５号 | ACCEPTED: 岡山県岡山市北区西崎本町7番5号 | resolved 4 candidate municipalities to 岡山県岡山市北区 by town '西崎本町' |
| 静岡県浜松市高林町８９番地の３ | ACCEPTED: 静岡県浜松市高林町89番地の3 | town '高林町' is not registered in any ward of 浜松市 |
| 福島県安達郡本宮町字下町１２番地 | ACCEPTED: 福島県本宮市字下町12番地 | 本宮町 no longer exists; its area is now part of 福島県本宮市 |
| 静岡県浜松市佐藤町７０８番地 | ACCEPTED: 静岡県浜松市佐藤町708番地 | town '佐藤町' is not registered in any ward of 浜松市 |
| 大阪府堺市土師町２９４５番地 | ACCEPTED: 大阪府堺市中区土師町2945番地 | resolved 7 candidate municipalities to 大阪府堺市中区 by town '土師町' |

**full: rejected: MALFORMED** (192)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 広島県呉市中通九丁目５番地 | MALFORMED: 広島県呉市中通9丁目5番地 | 中通 has only 1–4丁目; 9丁目 does not exist |
| 岐阜県土岐市泉町久尻三十二丁目７番地 | MALFORMED: 岐阜県土岐市泉町久尻32丁目7番地 | 泉町久尻 is not divided into 丁目; 32丁目 does not exist |
| 愛知県名古屋市中村区牧野町八丁目２８番地 | MALFORMED: 愛知県名古屋市中村区牧野町8丁目28番地 | 牧野町 has only 2–3丁目; 8丁目 does not exist |
| 福岡県北九州市若松区本町７丁目４９０番地 | MALFORMED: 福岡県北九州市若松区本町7丁目490番地 | 本町 has only 1–3丁目; 7丁目 does not exist |
| 和歌山県和歌山市黒田５丁目１番２０号 | MALFORMED: 和歌山県和歌山市黒田5丁目1番20号 | 黒田 has only 1–2丁目; 5丁目 does not exist |
| 広島県呉市本通十三丁目１４番地 | MALFORMED: 広島県呉市本通13丁目14番地 | 本通 has only 1–8丁目; 13丁目 does not exist |

**full: wrong** (6)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 福岡県福岡市中央区南区井尻二丁目１５番１５号 | ACCEPTED: 福岡県福岡市南区井尻2丁目15番15号 | two municipalities are written; read the second, 福岡市南区, where the town is registered |
| 鹿児島県鹿児島市奄美市名瀬伊津部６１０番地 | ACCEPTED: 鹿児島県奄美市名瀬伊津部610番地 | two municipalities are written; read the second, 奄美市, where the town is registered |
| 岐阜県羽島市岐南町上印食八丁目１０４レジデンス寺田５０６号室 | ACCEPTED: 岐阜県羽島郡岐南町上印食8丁目104番 レジデンス寺田 506号室 | two municipalities are written; read the second, 岐南町, where the town is registered |
| 徳島県美馬市つるぎ町半田字中藪２６７番地１ | ACCEPTED: 徳島県美馬郡つるぎ町半田字中藪267番地の1 | two municipalities are written; read the second, つるぎ町, where the town is registered |
| 千葉県山武市芝山町小池２７００－２６ＳＨＩＢＡＳＥＮＣＯ－ＯＰ－１０３ | ACCEPTED: 千葉県山武郡芝山町小池2700番26号 SHIBASENCO-OP 103 | two municipalities are written; read the second, 芝山町, where the town is registered |
| 埼玉県入間市越生町越生３９２－６ | ACCEPTED: 埼玉県入間郡越生町越生392番地の6 | two municipalities are written; read the second, 越生町, where the town is registered |

**no prefecture: ambiguous, truth listed** (12,284)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 中央区日本橋２丁目５番１号日本橋高島屋三井ビルディング | AMBIGUOUS: 中央区日本橋2丁目5番1号 日本橋高島屋三井ビルディング | town narrowed 11 candidate municipalities to 2 |
| 府中市府中町１２２番地１ | AMBIGUOUS: 府中市府中町122番地の1 | Omitted prefecture matches 2 statutory municipalities. |
| 中央区日本橋１丁目２－１０ | AMBIGUOUS: 中央区日本橋1丁目2番10号 | town narrowed 11 candidate municipalities to 2 |
| 中央区（東京市京橋区銀座二丁目３番地－５） | AMBIGUOUS: 中央区 (東京市京橋区銀座2丁目3番地-5) | Omitted prefecture matches 11 statutory municipalities. |
| 中央区（東京都日本橋区茅場町一丁目８番地２） | AMBIGUOUS: 中央区 (東京都日本橋区茅場町1丁目8番地2) | Omitted prefecture matches 11 statutory municipalities. |
| 中央区（東京市日本橋区芳町一丁目１番地６） | AMBIGUOUS: 中央区 (東京市日本橋区芳町1丁目1番地6) | Omitted prefecture matches 11 statutory municipalities. |

**no prefecture: rejected: UNSUPPORTED** (480)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 西条市氷見甲堤塘 | UNSUPPORTED: 愛媛県西条市氷見甲堤塘 | '堤塘' after the town 氷見甲 is not part of an address |
| 志摩市磯部町 | UNSUPPORTED: 三重県志摩市磯部町 | town '磯部町' is not registered in 志摩市 |
| 京都市下京区朱雀分木町市有地 | UNSUPPORTED: 京都府京都市下京区朱雀分木町市有地 | '市有地' after the town 朱雀分木町 is not part of an address |
| 伊勢市（三重県宇治山田市岩間町外地引揚者協力今内 | UNSUPPORTED: 三重県伊勢市(三重県宇治山田市岩間町外地引揚者協力今内 | town '(三重県宇治山田市岩間町外地引揚者協力今内' is not registered in 伊勢市 |
| 上川郡比布町字比布市街地 | UNSUPPORTED: 北海道上川郡比布町字比布市街地 | town '字比布市街地' is not registered in 比布町 |
| 京都市下京区朱雀分木町市有地 | UNSUPPORTED: 京都府京都市下京区朱雀分木町市有地 | '市有地' after the town 朱雀分木町 is not part of an address |

**no prefecture: row carries a municipality code that no longer exists** (182)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 熊本市健軍本町４番８号 | ACCEPTED: 熊本県熊本市東区健軍本町4番8号 | resolved 5 candidate municipalities to 熊本県熊本市東区 by town '健軍本町' |
| 岡山市西崎本町７番５号 | ACCEPTED: 岡山県岡山市北区西崎本町7番5号 | resolved 4 candidate municipalities to 岡山県岡山市北区 by town '西崎本町' |
| 浜松市高林町８９番地の３ | ACCEPTED: 静岡県浜松市高林町89番地の3 | town '高林町' is not registered in any ward of 浜松市 |
| 安達郡本宮町字下町１２番地 | ACCEPTED: 福島県本宮市字下町12番地 | 本宮町 no longer exists; its area is now part of 福島県本宮市 |
| 浜松市佐藤町７０８番地 | ACCEPTED: 静岡県浜松市佐藤町708番地 | town '佐藤町' is not registered in any ward of 浜松市 |
| 堺市土師町２９４５番地 | ACCEPTED: 大阪府堺市中区土師町2945番地 | resolved 7 candidate municipalities to 大阪府堺市中区 by town '土師町' |

**no prefecture: rejected: MALFORMED** (178)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 呉市中通九丁目５番地 | MALFORMED: 広島県呉市中通9丁目5番地 | 中通 has only 1–4丁目; 9丁目 does not exist |
| 土岐市泉町久尻三十二丁目７番地 | MALFORMED: 岐阜県土岐市泉町久尻32丁目7番地 | 泉町久尻 is not divided into 丁目; 32丁目 does not exist |
| 名古屋市中村区牧野町八丁目２８番地 | MALFORMED: 愛知県名古屋市中村区牧野町8丁目28番地 | 牧野町 has only 2–3丁目; 8丁目 does not exist |
| 北九州市若松区本町７丁目４９０番地 | MALFORMED: 福岡県北九州市若松区本町7丁目490番地 | 本町 has only 1–3丁目; 7丁目 does not exist |
| 和歌山市黒田５丁目１番２０号 | MALFORMED: 和歌山県和歌山市黒田5丁目1番20号 | 黒田 has only 1–2丁目; 5丁目 does not exist |
| 呉市本通十三丁目１４番地 | MALFORMED: 広島県呉市本通13丁目14番地 | 本通 has only 1–8丁目; 13丁目 does not exist |

**no prefecture: wrong** (40)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 北区中里町４１番地 | ACCEPTED: 兵庫県神戸市北区中里町41番地 | resolved 11 candidate municipalities to 兵庫県神戸市北区 by town '中里町' |
| 北区中里町４６８番地 | ACCEPTED: 兵庫県神戸市北区中里町468番地 | resolved 11 candidate municipalities to 兵庫県神戸市北区 by town '中里町' |
| 中央区入船町一丁目１９番地 | ACCEPTED: 新潟県新潟市中央区入船町1丁目19番地 | resolved 11 candidate municipalities to 新潟県新潟市中央区 by town '入船町' |
| 北区中里町４７０番地 | ACCEPTED: 兵庫県神戸市北区中里町470番地 | resolved 11 candidate municipalities to 兵庫県神戸市北区 by town '中里町' |
| 中央区入船町三丁目７番地 | ACCEPTED: 新潟県新潟市中央区入船町3丁目7番地 | resolved 11 candidate municipalities to 新潟県新潟市中央区 by town '入船町' |
| 伊達市字大町一丁目８１番地 | ACCEPTED: 北海道伊達市字大町1丁目81番地 | resolved 2 candidate municipalities to 北海道伊達市 by town '大町' |

**with postal code: rejected: UNSUPPORTED** (449)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 〒793-0071 愛媛県西条市氷見甲堤塘 | UNSUPPORTED: 愛媛県西条市氷見甲堤塘 | '堤塘' after the town 氷見甲 is not part of an address |
| 〒517-0500 三重県志摩市磯部町 | UNSUPPORTED: 三重県志摩市磯部町 | town '磯部町' is not registered in 志摩市 |
| 〒600-8847 京都府京都市下京区朱雀分木町市有地 | UNSUPPORTED: 京都府京都市下京区朱雀分木町市有地 | '市有地' after the town 朱雀分木町 is not part of an address |
| 〒516-0000 三重県伊勢市（三重県宇治山田市岩間町外地引揚者協力今内 | UNSUPPORTED: 三重県伊勢市(三重県宇治山田市岩間町外地引揚者協力今内 | town '(三重県宇治山田市岩間町外地引揚者協力今内' is not registered in 伊勢市 |
| 〒078-0300 北海道上川郡比布町字比布市街地 | UNSUPPORTED: 北海道上川郡比布町字比布市街地 | town '字比布市街地' is not registered in 比布町 |
| 〒600-8847 京都府京都市下京区朱雀分木町市有地 | UNSUPPORTED: 京都府京都市下京区朱雀分木町市有地 | '市有地' after the town 朱雀分木町 is not part of an address |

**with postal code: rejected: MALFORMED** (174)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 〒737-0000 広島県呉市中通九丁目５番地 | MALFORMED: 広島県呉市中通9丁目5番地 | 中通 has only 1–4丁目; 9丁目 does not exist |
| 〒509-5142 岐阜県土岐市泉町久尻三十二丁目７番地 | MALFORMED: 岐阜県土岐市泉町久尻32丁目7番地 | 泉町久尻 is not divided into 丁目; 32丁目 does not exist |
| 〒453-0871 愛知県名古屋市中村区牧野町八丁目２８番地 | MALFORMED: 愛知県名古屋市中村区牧野町8丁目28番地 | 牧野町 has only 2–3丁目; 8丁目 does not exist |
| 〒640-8341 和歌山県和歌山市黒田５丁目１番２０号 | MALFORMED: 和歌山県和歌山市黒田5丁目1番20号 | 黒田 has only 1–2丁目; 5丁目 does not exist |
| 〒737-0000 広島県呉市本通十三丁目１４番地 | MALFORMED: 広島県呉市本通13丁目14番地 | 本通 has only 1–8丁目; 13丁目 does not exist |
| 〒460-0000 愛知県名古屋市中区新栄町八丁目３１番地 | MALFORMED: 愛知県名古屋市中区新栄町8丁目31番地 | 新栄町 has only 1–3丁目; 8丁目 does not exist |

**with postal code: row carries a municipality code that no longer exists** (170)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 〒862-0910 熊本県熊本市健軍本町４番８号 | ACCEPTED: 熊本県熊本市東区健軍本町4番8号 | resolved 5 candidate municipalities to 熊本県熊本市東区 by town '健軍本町' |
| 〒700-0056 岡山県岡山市西崎本町７番５号 | ACCEPTED: 岡山県岡山市北区西崎本町7番5号 | resolved 4 candidate municipalities to 岡山県岡山市北区 by town '西崎本町' |
| 〒430-0908 静岡県浜松市高林町８９番地の３ | ACCEPTED: 静岡県浜松市高林町89番地の3 | postal code 430-0908 is not in the Japan Post list |
| 〒969-1132 福島県安達郡本宮町字下町１２番地 | ACCEPTED: 福島県本宮市字下町12番地 | 本宮町 no longer exists; its area is now part of 福島県本宮市 |
| 〒599-8238 大阪府堺市土師町２９４５番地 | ACCEPTED: 大阪府堺市中区土師町2945番地 | resolved 7 candidate municipalities to 大阪府堺市中区 by town '土師町' |
| 〒599-8238 大阪府堺市土師町２９７１番地 | ACCEPTED: 大阪府堺市中区土師町2971番地 | resolved 7 candidate municipalities to 大阪府堺市中区 by town '土師町' |

**town: no town written** (32,406)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 東京都中央区（東京市京橋区銀座二丁目３番地－５） | ACCEPTED: 東京都中央区 (東京市京橋区銀座2丁目3番地-5) | Local government entity verified against official statutory registry. |
| 東京都墨田区（本所区向島小梅町１４８番地） | ACCEPTED: 東京都墨田区 (本所区向島小梅町148番地) | Local government entity verified against official statutory registry. |
| 東京都墨田区（本所区柳原町二丁目５２番地） | ACCEPTED: 東京都墨田区 (本所区柳原町2丁目52番地) | Local government entity verified against official statutory registry. |
| 長野県安曇野市（明科町）３７６８番地 | ACCEPTED: 長野県安曇野市3768番地 (明科町) | Local government entity verified against official statutory registry. |
| 兵庫県神戸市兵庫区（神戸市兵庫東栁原町７９番屋敷） | ACCEPTED: 兵庫県神戸市兵庫区 (神戸市兵庫東栁原町79番屋敷) | Local government entity verified against official statutory registry. |
| 愛知県名古屋市港区（名古屋市南区海岸通四丁目２番地） | ACCEPTED: 愛知県名古屋市港区 (名古屋市南区海岸通4丁目2番地) | Local government entity verified against official statutory registry. |

**town: town not in the registry** (22,095)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 宮城県石巻市湊東２丁目８番地１ | ACCEPTED: 宮城県石巻市湊東2丁目8番地の1 | town '湊東' is not registered in 石巻市; a town of that name exists in 1 other municipality(ies) of this prefecture |
| 山梨県山梨市牧丘倉科１３７５番地 | ACCEPTED: 山梨県山梨市牧丘倉科1375番地 | town '牧丘倉科' is not registered in 山梨市 |
| 高知県高知市北萩町７番地４ | ACCEPTED: 高知県高知市北萩町7番地の4 | town '北萩町' is not registered in 高知市 |
| 福井県福井市花堂町東一丁目１０－２１ | ACCEPTED: 福井県福井市花堂町東1丁目10番21号 | town '花堂町東' is not registered in 福井市 |
| 北海道川上郡標茶町字コツタロ５４番地２ | ACCEPTED: 北海道川上郡標茶町字コツタロ54番地の2 | town '字コツタロ' is not registered in 標茶町 |
| 神奈川県小田原市新玉三丁目４８０番地 | ACCEPTED: 神奈川県小田原市新玉3丁目480番地 | town '新玉' is not registered in 小田原市 |

**postal: not filled in** (48,844)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 京都府京都市中京区柳馬場三条下ル槌屋町８３番地 | ACCEPTED: 京都府京都市中京区柳馬場三条下ル槌屋町83番地 | '槌屋町' occurs 2 times in 京都市中京区 |
| 北海道札幌市白石区本郷通１２丁目北２番７号 | ACCEPTED: 北海道札幌市白石区本郷通十二丁目北2番7号 | Municipality and town verified against official registries. |
| 愛媛県今治市桜井甲１０８３番地７ | ACCEPTED: 愛媛県今治市桜井甲1083番地の7 | Municipality and town verified against official registries. |
| 福岡県北九州市八幡東区前田２丁目３番１８号 | ACCEPTED: 福岡県北九州市八幡東区前田2丁目3番18号 | Municipality, town and 丁目 verified against official registries. |
| 栃木県那須郡那須町大字高久丙３番地２２ | ACCEPTED: 栃木県那須郡那須町大字高久丙3番地の22 | Municipality and town verified against official registries. |
| 新潟県上越市大豆２丁目２番３１号 | ACCEPTED: 新潟県上越市大豆2丁目2番31号 | Municipality, town and 丁目 verified against official registries. |

**postal: filled in, different from registered** (9,204)

| Input | JADEN | Message |
| :--- | :--- | :--- |
| 東京都練馬区西大泉町四丁目１８番９号 | ACCEPTED: 東京都練馬区西大泉4丁目18番9号 | read '西大泉町' as the registered town 西大泉 |
| 神奈川県相模原市中央区下九沢７５７－２３５２ | ACCEPTED: 神奈川県相模原市中央区下九沢 | postal code 757-2352 is not in the Japan Post list |
| 埼玉県八潮市大字二丁目１７１番地 | ACCEPTED: 埼玉県八潮市大字2丁目171番地 | Municipality, town and 丁目 verified against official registries. |
| 埼玉県八潮市大字二丁目３８２番地５ | ACCEPTED: 埼玉県八潮市大字2丁目382番地の5 | Municipality, town and 丁目 verified against official registries. |
| 北海道空知郡中富良野町字中富良野東３線北十七号 | ACCEPTED: 北海道空知郡中富良野町字中富良野東三線北17番地 | Municipality and town verified against official registries. |
| 福岡県福岡市南区大字横手南町一丁目１１ | ACCEPTED: 福岡県福岡市南区大字横手南町1丁目11番 | 横手南町 is not divided into 丁目 in the registry; 1丁目 is not listed (it may be a 字 name or newer than the data) |

