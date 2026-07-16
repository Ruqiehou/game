from __future__ import annotations

from ck_engine.core import AttributeSet, GameDate
from ck_engine.world import Gender, Terrain, TitleTier, World


class Scenario1066:
    @staticmethod
    def build() -> World:
        world = World(GameDate(1066, 1, 1))

        godwin = world.create_dynasty("戈德温")
        normandy = world.create_dynasty("诺曼")
        wessex = world.create_dynasty("威塞克斯")
        mercia = world.create_dynasty("麦西亚")
        northumbria = world.create_dynasty("诺森布里亚")
        flanders = world.create_dynasty("佛兰德")
        bretagne = world.create_dynasty("布列塔尼")

        for did, color, motto in [
            (godwin, (200, 50, 50), "天佑英格兰"),
            (normandy, (50, 50, 200), "征服者的意志"),
            (mercia, (40, 140, 60), "中部之心"),
            (northumbria, (90, 90, 140), "北境不屈"),
        ]:
            d = world.dynasties[did]
            d.color = color
            d.motto = motto

        middlesex = world.create_county("米德尔塞克斯", Terrain.FARMLAND)
        wessex_c = world.create_county("威塞克斯", Terrain.PLAINS)
        kent = world.create_county("肯特", Terrain.COASTAL)
        mercia_c = world.create_county("麦西亚", Terrain.FARMLAND)
        york = world.create_county("约克", Terrain.HILLS)
        northumbria_c = world.create_county("诺森布里亚", Terrain.HILLS)
        normandy_c = world.create_county("诺曼底", Terrain.COASTAL)
        rouen = world.create_county("鲁昂", Terrain.FARMLAND)
        east_anglia = world.create_county("东盎格利亚", Terrain.WETLAND)
        cornwall = world.create_county("康沃尔", Terrain.HILLS)
        sussex = world.create_county("苏塞克斯", Terrain.COASTAL)
        lincoln = world.create_county("林肯", Terrain.PLAINS)
        caen = world.create_county("卡昂", Terrain.PLAINS)
        bayeux = world.create_county("贝叶", Terrain.HILLS)

        for a, b in [
            (middlesex, wessex_c),
            (middlesex, kent),
            (middlesex, mercia_c),
            (middlesex, east_anglia),
            (middlesex, sussex),
            (wessex_c, cornwall),
            (wessex_c, kent),
            (wessex_c, sussex),
            (mercia_c, york),
            (mercia_c, lincoln),
            (york, northumbria_c),
            (york, lincoln),
            (east_anglia, lincoln),
            (kent, sussex),
            (normandy_c, rouen),
            (normandy_c, caen),
            (rouen, bayeux),
            (caen, bayeux),
            (normandy_c, kent),
            (caen, sussex),
        ]:
            world.map.connect(a, b)

        for cid, dev, levies, tax, fort in [
            (middlesex, 28, 450, 2.2, 3),
            (wessex_c, 20, 320, 1.6, 2),
            (kent, 18, 280, 1.5, 2),
            (mercia_c, 16, 300, 1.4, 2),
            (york, 14, 260, 1.2, 2),
            (northumbria_c, 10, 220, 1.0, 2),
            (normandy_c, 24, 380, 1.9, 3),
            (rouen, 22, 300, 1.7, 2),
            (east_anglia, 12, 200, 1.1, 1),
            (cornwall, 8, 150, 0.8, 1),
            (sussex, 15, 240, 1.3, 2),
            (lincoln, 13, 230, 1.2, 1),
            (caen, 18, 270, 1.5, 2),
            (bayeux, 14, 200, 1.2, 2),
        ]:
            c = world.map.get(cid)
            if c:
                c.development = dev
                c.levies = levies
                c.tax = tax
                c.fort_level = fort
                c.buildings = ["庄园", "市场"]
                if fort >= 2:
                    c.buildings.append("城堡")

        k_england = world.create_title("英格兰", TitleTier.KINGDOM)
        d_wessex = world.create_title("威塞克斯公国", TitleTier.DUCHY)
        d_mercia = world.create_title("麦西亚公国", TitleTier.DUCHY)
        d_north = world.create_title("诺森布里亚公国", TitleTier.DUCHY)
        d_normandy = world.create_title("诺曼底公国", TitleTier.DUCHY)
        c_middlesex = world.create_title("米德尔塞克斯伯爵领", TitleTier.COUNTY)
        c_wessex = world.create_title("威塞克斯伯爵领", TitleTier.COUNTY)
        c_kent = world.create_title("肯特伯爵领", TitleTier.COUNTY)
        c_mercia = world.create_title("麦西亚伯爵领", TitleTier.COUNTY)
        c_york = world.create_title("约克伯爵领", TitleTier.COUNTY)
        c_north = world.create_title("诺森布里亚伯爵领", TitleTier.COUNTY)
        c_normandy = world.create_title("诺曼底伯爵领", TitleTier.COUNTY)
        c_rouen = world.create_title("鲁昂伯爵领", TitleTier.COUNTY)
        c_east = world.create_title("东盎格利亚伯爵领", TitleTier.COUNTY)
        c_cornwall = world.create_title("康沃尔伯爵领", TitleTier.COUNTY)
        c_sussex = world.create_title("苏塞克斯伯爵领", TitleTier.COUNTY)
        c_lincoln = world.create_title("林肯伯爵领", TitleTier.COUNTY)
        c_caen = world.create_title("卡昂伯爵领", TitleTier.COUNTY)
        c_bayeux = world.create_title("贝叶伯爵领", TitleTier.COUNTY)

        for county, title in [
            (middlesex, c_middlesex),
            (wessex_c, c_wessex),
            (kent, c_kent),
            (mercia_c, c_mercia),
            (york, c_york),
            (northumbria_c, c_north),
            (normandy_c, c_normandy),
            (rouen, c_rouen),
            (east_anglia, c_east),
            (cornwall, c_cornwall),
            (sussex, c_sussex),
            (lincoln, c_lincoln),
            (caen, c_caen),
            (bayeux, c_bayeux),
        ]:
            world.attach_county_to_title(county, title)

        for t in [c_middlesex, c_wessex, c_kent, c_cornwall, c_sussex, c_east]:
            world.set_vassal(t, d_wessex)
        world.set_vassal(c_mercia, d_mercia)
        world.set_vassal(c_lincoln, d_mercia)
        for t in [c_york, c_north]:
            world.set_vassal(t, d_north)
        for t in [c_normandy, c_rouen, c_caen, c_bayeux]:
            world.set_vassal(t, d_normandy)
        for t in [d_wessex, d_mercia, d_north]:
            world.set_vassal(t, k_england)

        harold = world.create_character("哈罗德·戈德温森", godwin, Gender.MALE, GameDate(1022, 1, 1))
        edith = world.create_character("伊迪丝·斯旺内斯", godwin, Gender.FEMALE, GameDate(1025, 1, 1))
        godwine_son = world.create_character("戈德温·哈罗德森", godwin, Gender.MALE, GameDate(1048, 1, 1))
        edmund = world.create_character("埃德蒙·哈罗德森", godwin, Gender.MALE, GameDate(1050, 1, 1))
        gytha = world.create_character("吉莎·哈罗德森", godwin, Gender.FEMALE, GameDate(1053, 1, 1))
        tostig = world.create_character("托斯蒂格·戈德温森", godwin, Gender.MALE, GameDate(1026, 1, 1))
        gyrth = world.create_character("吉尔思·戈德温森", godwin, Gender.MALE, GameDate(1032, 1, 1))
        leofwine = world.create_character("利奥夫温·戈德温森", godwin, Gender.MALE, GameDate(1035, 1, 1))
        william = world.create_character("威廉·征服者", normandy, Gender.MALE, GameDate(1028, 1, 1))
        matilda = world.create_character("佛兰德的玛蒂尔达", flanders, Gender.FEMALE, GameDate(1031, 1, 1))
        robert = world.create_character("罗伯特·柯索斯", normandy, Gender.MALE, GameDate(1051, 1, 1))
        william_rufus = world.create_character("威廉·鲁弗斯", normandy, Gender.MALE, GameDate(1056, 1, 1))
        adela = world.create_character("阿黛拉·诺曼", normandy, Gender.FEMALE, GameDate(1062, 1, 1))
        odo = world.create_character("贝叶的奥多", normandy, Gender.MALE, GameDate(1030, 1, 1))
        roger = world.create_character("罗杰·德·蒙哥马利", normandy, Gender.MALE, GameDate(1035, 1, 1))
        william_fitz = world.create_character("威廉·菲茨奥斯本", normandy, Gender.MALE, GameDate(1030, 1, 1))
        edwin = world.create_character("埃德温·麦西亚", mercia, Gender.MALE, GameDate(1035, 1, 1))
        morcar = world.create_character("莫卡·诺森布里亚", northumbria, Gender.MALE, GameDate(1038, 1, 1))
        edgar = world.create_character("埃德加·威塞克斯", wessex, Gender.MALE, GameDate(1051, 1, 1))
        aldgyth = world.create_character("奥尔吉斯", mercia, Gender.FEMALE, GameDate(1040, 1, 1))
        eava = world.create_character("诺曼侍女艾娃", normandy, Gender.FEMALE, GameDate(1045, 1, 1))
        ealdgyth = world.create_character("埃德温之妹埃尔德吉斯", mercia, Gender.FEMALE, GameDate(1042, 1, 1))
        alan = world.create_character("阿兰·布列塔尼", bretagne, Gender.MALE, GameDate(1040, 1, 1))
        stiguand = world.create_character("大主教斯蒂甘德", wessex, Gender.MALE, GameDate(1000, 1, 1))
        waltheof = world.create_character("沃尔西奥夫", northumbria, Gender.MALE, GameDate(1050, 1, 1))

        for cid in [
            harold, edith, godwine_son, edmund, gytha, tostig, gyrth, leofwine,
            edwin, morcar, edgar, aldgyth, ealdgyth, stiguand, waltheof,
        ]:
            ch = world.character(cid)
            if ch:
                ch.culture, ch.faith = 0, 0
        for cid in [
            william, matilda, robert, william_rufus, adela, odo, roger,
            william_fitz, eava, alan,
        ]:
            ch = world.character(cid)
            if ch:
                ch.culture, ch.faith = 1, 0

        world.set_parents(godwine_son, harold, edith)
        world.set_parents(edmund, harold, edith)
        world.set_parents(gytha, harold, edith)
        world.set_parents(robert, william, matilda)
        world.set_parents(william_rufus, william, matilda)
        world.set_parents(adela, william, matilda)
        world.marry(harold, edith)
        world.marry(william, matilda)
        world.marry(edwin, aldgyth)

        def set_attrs(cid, attrs, gold, prestige, traits):
            ch = world.character(cid)
            if not ch:
                return
            ch.base_attrs = attrs
            ch.gold = gold
            ch.prestige = prestige
            for t in traits:
                if t not in ch.traits:
                    ch.traits.append(t)

        set_attrs(harold, AttributeSet(12, 16, 11, 10, 9, 14), 220, 320, [1, 6])
        set_attrs(william, AttributeSet(11, 18, 14, 13, 10, 15), 280, 420, [1, 6, 9])
        set_attrs(edwin, AttributeSet(10, 12, 13, 8, 8, 10), 120, 150, [3])
        set_attrs(morcar, AttributeSet(8, 13, 9, 9, 7, 12), 100, 140, [1])
        set_attrs(tostig, AttributeSet(7, 14, 8, 12, 7, 13), 80, 90, [2, 11])
        set_attrs(odo, AttributeSet(10, 11, 12, 14, 13, 8), 90, 110, [2, 8])
        set_attrs(stiguand, AttributeSet(12, 4, 10, 11, 16, 3), 60, 80, [8, 3])

        world.grant_title(k_england, harold)
        world.grant_title(d_wessex, harold)
        world.grant_title(c_middlesex, harold)
        world.grant_title(c_wessex, harold)
        world.grant_title(c_kent, gyrth)
        world.grant_title(c_east, leofwine)
        world.grant_title(c_cornwall, harold)
        world.grant_title(c_sussex, harold)
        world.grant_title(d_mercia, edwin)
        world.grant_title(c_mercia, edwin)
        world.grant_title(c_lincoln, edwin)
        world.grant_title(d_north, morcar)
        world.grant_title(c_york, morcar)
        world.grant_title(c_north, morcar)
        world.grant_title(d_normandy, william)
        world.grant_title(c_normandy, william)
        world.grant_title(c_rouen, william)
        world.grant_title(c_caen, william)
        world.grant_title(c_bayeux, odo)

        world.set_vassal(d_mercia, k_england)
        world.set_vassal(d_north, k_england)
        world.set_vassal(d_wessex, k_england)
        world.set_vassal(c_kent, d_wessex)
        world.set_vassal(c_east, d_wessex)
        world.set_vassal(c_bayeux, d_normandy)

        for duchy, counties in [
            (d_wessex, [middlesex, wessex_c, kent, cornwall, east_anglia, sussex]),
            (d_mercia, [mercia_c, lincoln]),
            (d_north, [york, northumbria_c]),
            (d_normandy, [normandy_c, rouen, caen, bayeux]),
            (
                k_england,
                [
                    middlesex, wessex_c, kent, mercia_c, york, northumbria_c,
                    east_anglia, cornwall, sussex, lincoln,
                ],
            ),
        ]:
            t = world.title(duchy)
            if t:
                for cid in counties:
                    if cid not in t.counties:
                        t.counties.append(cid)

        world.modify_opinion(tostig, harold, -40)
        world.modify_opinion(harold, tostig, -25)
        world.modify_opinion(edwin, harold, -5)
        world.modify_opinion(morcar, harold, -8)
        world.modify_opinion(william, harold, -30)
        world.modify_opinion(harold, william, -20)
        world.modify_opinion(odo, william, 25)
        world.modify_opinion(roger, william, 20)
        world.modify_opinion(william_fitz, william, 22)
        world.modify_opinion(gyrth, harold, 30)
        world.modify_opinion(leofwine, harold, 28)

        world.push_log("1066 年场景已加载：哈罗德统治英格兰，威廉虎视眈眈。")
        world.push_log("托斯蒂格与兄长不和，北方伯爵心怀观望。")
        return world
