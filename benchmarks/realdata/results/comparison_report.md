# Comparison with other tools on real addresses

Every tool gets the same text and is scored by the same rule (see `compare_tools.py`). **Right**: names the row's own municipality. **Wrong**: names another one. **No answer**: returns no single municipality (JADEN: ambiguous or rejected). **Precision**: right / answered.

| Input | Tool | Addresses | Right | Wrong | Wrong, tools disagree | City, not ward | No answer | Precision |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Care offices, as typed | JADEN | 223,146 | **97.89%** | 136 (0.06%) | **17** | 0 | 4,581 (2.05%) | 99.94% |
|  | geolonia | 223,146 | **94.76%** | 345 (0.15%) | **226** | 0 | 11,338 (5.08%) | 99.84% |
|  | jageocoder | 223,146 | **98.53%** | 2,039 (0.91%) | **1,920** | 133 | 1,106 (0.50%) | 99.02% |
| Care offices, with the row's prefecture and municipality | JADEN | 223,146 | **99.88%** | 123 (0.06%) | **16** | 0 | 145 (0.06%) | 99.94% |
|  | geolonia | 223,146 | **99.40%** | 109 (0.05%) | **2** | 0 | 1,234 (0.55%) | 99.95% |
|  | jageocoder | 223,146 | **99.48%** | 188 (0.08%) | **81** | 118 | 861 (0.39%) | 99.86% |
| Companies, registered address | JADEN | 100,992 | **99.99%** | 0 (0.00%) | **0** | 0 | 13 (0.01%) | 100.00% |
|  | geolonia | 100,992 | **99.99%** | 0 (0.00%) | **0** | 0 | 12 (0.01%) | 100.00% |
|  | jageocoder | 100,992 | **100.00%** | 0 (0.00%) | **0** | 0 | 0 (0.00%) | 100.00% |
| Companies, without the prefecture | JADEN | 100,992 | **99.73%** | 1 (0.00%) | **1** | 0 | 267 (0.26%) | 100.00% |
|  | geolonia | 100,992 | **99.96%** | 24 (0.02%) | **24** | 0 | 14 (0.01%) | 99.98% |
|  | jageocoder | 100,992 | **99.92%** | 78 (0.08%) | **78** | 0 | 1 (0.00%) | 99.92% |
| Companies, postal code in front | JADEN | 100,938 | **99.99%** | 0 (0.00%) | **0** | 0 | 9 (0.01%) | 100.00% |
|  | geolonia | 100,938 | **0.00%** | 0 (0.00%) | **0** | 0 | 100,938 (100.00%) | – |
|  | jageocoder | 100,938 | **0.00%** | 107 (0.11%) | **107** | 0 | 100,831 (99.89%) | 0.00% |

**Wrong, tools disagree** leaves out the wrong answers that every tool shares: when all of them read the text as the same other municipality, the row's own code is most likely what is wrong (for example `北海道網走郡美幌町…` filed under 網走市). The examples below leave them out too.

JADEN's "no answer" includes its ambiguous results, where it returns the possible municipalities instead of one; the row's municipality is in that list for 4,127 (care offices, as typed), 23 (care offices, with the row's prefecture and municipality), 254 (companies, without the prefecture).

102 of jageocoder's wrong answers name a municipality that no longer exists (for example 浜松市中区, abolished in 2024): it read an old address under its old name.

Left out for every tool: 45 inputs whose row carries a municipality code that no longer exists.

## Examples of wrong answers (and of a designated city named without its ward)

**Care offices, as typed, JADEN** (8 of 17, spread over the data)

- `肥塚四丁目150番` → 埼玉県熊谷市 (row: 埼玉県越谷市)
- `御車道通清和院口上る東側梶井町457-1` → 京都府京都市上京区 (row: 京都府京都市右京区)
- `西宮市1丁目6番25号` → 兵庫県西宮市 (row: 福岡県行橋市)
- `舞原344-2あすなろ熊本壱番館` → 佐賀県有田町 (row: 熊本県熊本市南区)
- `大阪巣堺市中区東山62番地1　2階` → 大阪府堺市中区 (row: 大阪府堺市東区)
- `兵庫県赤穂市上郡町竹万381-5シャイン上郡` → 兵庫県上郡町 (row: 兵庫県赤穂市)
- `熊本県熊本市流通団地2-20-1センコービル2階` → 熊本県熊本市南区 (row: 熊本県熊本市中央区)
- `丹波市町295` → 兵庫県丹波市 (row: 奈良県天理市)

**Care offices, as typed, geolonia** (8 of 226, spread over the data)

- `小川町上小川字川原28-1` → 埼玉県小川町 (row: 福島県いわき市)
- `日の出町１−６−４７ビバリーポート一階` → 東京都日の出町 (row: 福岡県北九州市小倉南区)
- `中央区南8条西7丁目1782-5小林ビル1階` → 東京都中央区 (row: 北海道札幌市中央区)
- `瑞穂町1-7-24` → 東京都瑞穂町 (row: 山口県下松市)
- `神戸町914番地` → 岐阜県神戸町 (row: 愛知県名古屋市熱田区)
- `北区北五葉１丁目２－１５栄規ビル１０５` → 東京都北区 (row: 兵庫県神戸市北区)
- `一宮町651-11` → 千葉県一宮町 (row: 香川県高松市)
- `中山町1470-1` → 山形県中山町 (row: 鹿児島県鹿児島市)

**Care offices, as typed, jageocoder** (8 of 400+, spread over the data)

- `北3条西12丁目2－2` → 北海道岩見沢市 (row: 北海道札幌市中央区)
- `中曽根2373番地セントラルパーク牧野` → 福島県須賀川市 (row: 富山県高岡市)
- `千代田五丁目15番12号千代田ヒルズ3C` → 千葉県四街道市 (row: 愛知県名古屋市中区)
- `三条通烏丸東入梅忠町20-1烏丸アネックス0402` → 愛知県一宮市 (row: 京都府京都市中京区)
- `森本1丁目8-19` → 愛知県一宮市 (row: 兵庫県伊丹市)
- `新保589--7ｴｽﾃｰﾄ新保B101` → 長野県中野市 (row: 岡山県岡山市南区)
- `植木757-7` → 神奈川県鎌倉市 (row: 福岡県直方市)
- `小野1丁目11-29ＧＩＮＹＡビル102` → 岐阜県大垣市 (row: 鹿児島県鹿児島市)

**Care offices, with the row's prefecture and municipality, JADEN** (8 of 16, spread over the data)

- `茨城県茨城町つくばみらい市陽光台４丁目９番地3` → 茨城県つくばみらい市 (row: 茨城県茨城町)
- `広島県熊野町呉市音戸町畑１丁目２番５１号` → 広島県呉市 (row: 広島県熊野町)
- `埼玉県入間市毛呂山町岩井西5丁目5-19第二いづも荘1号棟` → 埼玉県毛呂山町 (row: 埼玉県入間市)
- `茨城県駒場3丁目7－15` → 茨城県取手市 (row: 茨城県阿見町)
- `兵庫県赤穂市上郡町竹万381-5シャイン上郡` → 兵庫県上郡町 (row: 兵庫県赤穂市)
- `茨城県阿見町牛久市柏田町１５８９－３` → 茨城県牛久市 (row: 茨城県阿見町)
- `茨城県阿見町稲敷郡美浦村大字土屋字山下1979番地` → 茨城県美浦村 (row: 茨城県阿見町)
- `北海道上川町帯広市西22条南3丁目33-1` → 北海道帯広市 (row: 北海道上川町)

**Care offices, with the row's prefecture and municipality, geolonia** (2 of 2, spread over the data)

- `北海道札幌市東区北区篠路1条2丁目2-28` → 北海道札幌市東区 (row: 北海道札幌市北区)
- `岐阜県岐阜市関市稲口776-1介護老人保健施設　花咲き庵` → 岐阜県岐阜市 (row: 岐阜県関市)

**Care offices, with the row's prefecture and municipality, jageocoder** (8 of 199, spread over the data)

- `北海道札幌市あいの里4条5丁目4－10` → 北海道札幌市 (row: 北海道札幌市北区)
- `大阪府大阪市山王三丁目16-25エスポワール102` → 大阪府大阪市 (row: 大阪府大阪市西成区)
- `兵庫県神戸市八幡町2ｰ2ｰ6八幡ハイム1階` → 兵庫県神戸市 (row: 兵庫県神戸市灘区)
- `愛知県名古屋市四軒家一丁目1576番地レーベン豊1F　102号室` → 愛知県名古屋市 (row: 愛知県名古屋市守山区)
- `岡山県岡山市楢津500-5` → 岡山県岡山市 (row: 岡山県岡山市北区)
- `静岡県浜松市西区大山町2957-1` → unknown:静岡県浜松市西区 (row: 静岡県浜松市中央区)
- `静岡県静岡市岡部町岡部437番地の3` → 静岡県静岡市 (row: 静岡県藤枝市)
- `福岡県北九州市　小倉南区　葛原東2-14-2` → 福岡県北九州市 (row: 福岡県北九州市小倉南区)

**Companies, without the prefecture, JADEN** (1 of 1, spread over the data)

- `中央区入船町一丁目７番地` → 新潟県新潟市中央区 (row: 東京都中央区)

**Companies, without the prefecture, geolonia** (8 of 24, spread over the data)

- `伊達市旭町６３番地` → 福島県伊達市 (row: 北海道伊達市)
- `伊達市館山下町１番地６８` → 福島県伊達市 (row: 北海道伊達市)
- `伊達市長和町６９３番地２` → 福島県伊達市 (row: 北海道伊達市)
- `府中市南町２丁目２７番地の５` → 広島県府中市 (row: 東京都府中市)
- `府中市府中町１丁目５番６号高橋ビル３Ｆ` → 広島県府中市 (row: 東京都府中市)
- `府中市南町４丁目１４番２号レジデンス佐伯Ⅱ１０１号室` → 広島県府中市 (row: 東京都府中市)
- `府中市府中町１丁目３４番地の４` → 広島県府中市 (row: 東京都府中市)
- `府中市府中町２丁目９番地の１プレスティージ府中７０４` → 広島県府中市 (row: 東京都府中市)

**Companies, without the prefecture, jageocoder** (8 of 78, spread over the data)

- `伊達市字上町３６番地` → 北海道伊達市 (row: 福島県伊達市)
- `中央区（東京市京橋区南鞘町１３番地）` → 北海道札幌市中央区 (row: 東京都中央区)
- `中央区（東京市日本橋区村松町１３番地）` → 北海道札幌市中央区 (row: 東京都中央区)
- `中央区（東京都日本橋区通二丁目２番地５）` → 北海道札幌市中央区 (row: 東京都中央区)
- `中央区（東京市京橋区松屋町一丁目８番地）` → 北海道札幌市中央区 (row: 東京都中央区)
- `中央区（東京市日本橋区室町三丁目４番地ノ６）` → 北海道札幌市中央区 (row: 東京都中央区)
- `中央区（東京市京橋区銀座二丁目２番地越後屋ビル１階）` → 北海道札幌市中央区 (row: 東京都中央区)
- `中央区（東京市日本橋区横山町一丁目５番地）` → 北海道札幌市中央区 (row: 東京都中央区)

**Companies, postal code in front, jageocoder** (8 of 107, spread over the data)

- `〒230-0048 神奈川県横浜市鶴見区本町通４丁目１７１番地の１７ライオンズマンション鶴見本町通り` → 埼玉県川口市 (row: 神奈川県横浜市鶴見区)
- `〒680-0142 鳥取県鳥取市国府町麻生２３２番地` → 埼玉県川口市 (row: 鳥取県鳥取市)
- `〒680-0947 鳥取県鳥取市湖山町西３丁目５３１－６` → 埼玉県川口市 (row: 鳥取県鳥取市)
- `〒680-0833 鳥取県鳥取市末広温泉町４６１番地` → 埼玉県川口市 (row: 鳥取県鳥取市)
- `〒680-0911 鳥取県鳥取市千代水３丁目１０５番地` → 埼玉県川口市 (row: 鳥取県鳥取市)
- `〒680-0001 鳥取県鳥取市浜坂４丁目１１番２０号` → 埼玉県川口市 (row: 鳥取県鳥取市)
- `〒680-0941 鳥取県鳥取市湖山町北２丁目８８６－１０３` → 埼玉県川口市 (row: 鳥取県鳥取市)
- `〒680-0151 鳥取県鳥取市国府町宮下２４２番地` → 埼玉県川口市 (row: 鳥取県鳥取市)
