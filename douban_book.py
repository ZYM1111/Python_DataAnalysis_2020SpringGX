import os
from tqdm import tqdm
import pandas as pd
import re
import math
import pyecharts.options as opts
from pyecharts.charts import Bar, Line, Radar, Pie, Timeline, Funnel


def MergeFiles() -> list:
    '''
    合并多个excel文件，最后写入一个txt文件中\n
    :return: 每个元素是csv格式文件每一行切分过后的列表的列表
    '''
    dir = "./RawData"  # 设置工作路径
    frames = []  # 每个文件读成一个dataframe，存到frames列表中
    for root, dirs, files in os.walk(dir):
        for file in tqdm(files):
            df = pd.read_excel(os.path.join(root, file))  # excel转换成DataFrame
            frames.append(df)
    result = pd.concat(frames) # 合并所有数据

    # 删除无用的列
    del result['图片地址']
    del result['URL入口']
    # 删除包含缺失值的行
    result_cleaned = result.dropna()
    # 删除重复值 六万行顿时变成三万行，猜测原因是原始数据是存放在多个excel表里的，名为“小说”的表和名为“鲁迅”的表会有重复内容
    result_cleaned = result_cleaned.drop_duplicates()
    # result_cleaned = result_cleaned.drop_duplicates(['书籍名'])

    # 不存在文件就生成文件，方便调试。已经存在的文件再生成会报错
    # 用'{'分隔，因为数据里本来就存在逗号，如 "阿宅, 你已經死了!"的形式(双引号里有逗号)
    # 如果用","分隔，后续也可以用正则表达式来匹配双引号中有逗号这样的字符串，其原生字符串表示为r'".*?,.*?"'
    # 但是匹配出结果后，一行信息可能书名和出版信息都是双引号里有逗号的形式，也可能之后出版信息是这样的格式，再对应回去就很难实现
    if not os.path.exists("./HandledData/merged.txt"):
        result_cleaned.to_csv('./HandledData/merged.txt', sep='{', index=False)

    # 读合并过后的txt文件，生成列表，每个元素是每一行切分过后的列表，
    # 如['哈利·波特与魔法石', '[英] J. K. 罗琳 / 苏农 / 人民文学出版社 / 2000-9 / 19.50元', '9.0']
    # 本来读文件是写在DataClean函数里的，现在放到这里感觉有点......先写文件，然后又读文件，感觉多此一举了
    with open("./HandledData/merged.txt", encoding='utf-8') as file:
        file.readline()  # 让文件的指针指向第二行，把列名跳过，后续再定义
        ls = [line.strip().split('{') for line in file]

    print("Successfully ran MergeFiles")
    return ls



def DataClean(ls: list) -> list:
    '''
    清除无效数据：书名、出版信息、评价星数三者不全的;出版信息不全的;正则匹配不到年份的;正则匹配不到价格的\n
    :param ls: 原列表，存放原始数据
    :return: new_ls
    '''

    # 用很原始的方法，符合条件者加入新列表，不符合的跳过
    new_ls = []
    yearRegex = re.compile(r'(2|1)\d{3}')  # 正则表达式匹配年份,待匹配字符串的格式有"y-m-d"、"m-d-y",甚至还有July 16, 2005
    priceRegex = re.compile(r'\d+(\.\d+)?')  # 正则表达式匹配价格,待匹配格式：19.50元， USD 10.99等
    for idx in tqdm(range(len(ls))):
        if len(ls[idx]) == 3 and len(ls[idx][1].split('/')) >= 4 and \
                yearRegex.search(ls[idx][1].split('/')[-2].strip()) and \
                priceRegex.search(ls[idx][1].split('/')[-1].strip()):
            # if条件从左至右:书名、出版信息、星数都全;出版信息全;正则可以匹配到年份;正则可以匹配到价格
            new_ls.append(ls[idx])
            # new_ls的每一项的格式: ['哈利·波特与魔法石', '[英] J. K. 罗琳 / 苏农 / 人民文学出版社 / 2000-9 / 19.50元', '9.0']
    print("Successfully ran DataClean")
    return new_ls



def GenerateListAndDf(new_ls: list) -> pd.DataFrame:
    '''
    生成书名、作者、出版日期、价格、评价星数的列表，以生成DataFrame\n
    :param new_ls: txt文件每一行切分后的列表
    :return: 列名是'title','author','time','price','points'的DataFrame
    '''

    # new_ls_1的每一项的格式: ['哈利·波特与魔法石', '[英] J. K. 罗琳 / 苏农 / 人民文学出版社 / 2000-9 / 19.50元', '9.0']
    yearRegex = re.compile(r'(2|1)\d{3}')  # 正则表达式匹配年份,待匹配字符串的格式有"y-m-d"、"m-d-y",甚至还有July 16, 2005


    author = [x[1].split('/')[0].strip() for x in tqdm(new_ls)]
    price = [x[1].split('/')[-1].strip() for x in tqdm(new_ls)]
    time = [int(yearRegex.search(x[1].split('/')[-2].strip()).group()) for x in tqdm(new_ls)]  # 出版日期只取到年份
    title = [x[0].strip() for x in tqdm(new_ls)]
    points = [float(x[2]) for x in tqdm(new_ls)]
    publisher = [x[1].split('/')[-3].strip() for x in tqdm(new_ls)]
    price = ConvertMoney(price)

    names = ['title', 'author', 'publisher', 'time', 'price', 'points']
    dic = dict(zip(names, [title, author, publisher, time, price, points]))
    Data = pd.DataFrame(dic)
    Data = Data.dropna()
    print("Successfully ran GenerateListAndDf")
    return Data



def ConvertMoney(price: list) -> list:
    '''
    将价格都换算成人民币为单位的\n
    :param price: 每个元素是一个字符串的列表
    :return: 每个元素是浮点数的列表
    '''
    priceRegex = re.compile(r'\d+(,\d+)*\.?\d*')  # 注意这里可能有三位分节法表示的数字
    markRegex = re.compile((r'[^\d]+'))  # # 匹配价格中代表货币种类的部分
    JapanList = ['税', '込', '円', '日', 'JP', 'NNT', 'Yen']  # 1日元=0.06632人民币
    TaiWanList = ['N.T.', 'NT', 'NTD', 'TWD', '台', '臺', 'N.T', 'nt']  # 1新台币=0.2370人民币
    SouthKoreaList = ['韩', 'KRW']  # 1韩元=0.005799人民币
    HKList = ['HK', '港', 'hk', 'H.K.']  # 1港元=0.9125人民币
    UKList = ['£', 'UK', 'uk', 'GBP']  # 1英镑=8.7757人民币
    EuropeList = ['EUROS', '€', 'EUR']  # 1欧元=7.6673人民币
    SingaporeList = ['新元']  # 1新加坡元=5.0076人民币
    ThailandList = ['THB', 'baht']  # 1泰铢=0.2196人民币
    MalaysiaList = ['RM']  # 1马来西亚林吉特=1.6335人民币
    CanadaList = ['CAD', 'CAN', 'CDN']  # 1加元=5.0771人民币
    USList = ['us', 'US', '美', '$']  # 1美元=7.0732人民币
    for i in tqdm(range(len(price))):
        match_mark = markRegex.search(price[i])  # 匹配价格中代表货币种类的部分
        match_value = priceRegex.search(price[i])  # 匹配价格的数值部分
        if match_mark and match_value:  # 事实上，match_value是恒为True的,它价格总不能没有阿拉伯数字而用文字表达吧
            mark = match_mark.group()
            value = float(match_value.group().replace(',', ''))  # 将匹配到的数值字符串中的','删除,再转为浮点型
            if any(x in mark for x in JapanList):
                value *= 0.06632
            elif any(x in mark for x in TaiWanList):
                value *= 0.2370
            elif any(x in mark for x in SouthKoreaList):
                value *= 0.005799
            elif any(x in mark for x in HKList):
                value *= 0.9125
            elif any(x in mark for x in UKList):
                value *= 8.7757
            elif any(x in mark for x in EuropeList):
                value *= 7.6673
            elif any(x in mark for x in SingaporeList):
                value *= 5.0076
            elif any(x in mark for x in ThailandList):
                value *= 0.2196
            elif any (x in mark for x in MalaysiaList):
                value *= 1.6335
            elif any(x in mark for x in CanadaList):
                value *= 5.0771
            elif any(x in mark for x in USList):  # 倒数第二个换算美元，因为"$"在上述的币种中也存在,"$"单独存在时表示美元
                value *= 7.0732
            else:
                value = value
        elif match_value:
            value = value
        price[i] = value
    print("Successfully ran ConvertMoney")
    return price



def RankOfCompositionNums(Data: pd.DataFrame) -> tuple:
    '''
    作品数量top20的作家\n
    :param Data: DataFrame
    :return: top20作家名称、作品数量、作品均分三个列表组成的元组
    '''

    # 作品数量前20的作家名称，因为简体繁体等原因，有重复，所以取前30，后续删除重复
    Top20WritersNames = Data.groupby('author').title.count().sort_values(ascending=False).index.to_list()[:30]
    del Top20WritersNames[27:29]
    del Top20WritersNames[23:25]
    del Top20WritersNames[16:22]
    # 作品数量top20的作家的作品数量，
    Top20WritersNums = Data.groupby('author').title.count().sort_values(ascending=False).to_list()[:30]
    del Top20WritersNums[27:29]
    del Top20WritersNums[23:25]
    del Top20WritersNums[16:22]
    # 所有作家的平均分的字典
    AvgPoints = Data.groupby('author').points.mean().to_dict()
    # 在所有作家的平均分里索引top20作家的均分 感觉这个方法很笨，应该可以用dataframe的方法直接做
    Top20WritersPoints = [AvgPoints[x] for x in tqdm(Top20WritersNames)]
    # print(Top20WritersPoints)
    # [8.420722891566275, 8.722807017543849, 7.2832258064516076, 8.807333333333334, 8.410954063604235,\
    # 7.803149606299215, 8.756916996047428, 8.098522167487682, 7.514427860696514, 6.998984771573604,\
    # 8.367724867724863, 8.31129032258064, 7.717741935483874, 8.101818181818176, 7.6331125827814565,\
    # 8.28992248062016, 7.616666666666671, 8.606896551724143, 7.670093457943924, 7.476237623762376,\
    # 8.765306122448976, 7.734020618556701]
    print("Successfully ran RankOfCompositionNums")
    return Top20WritersNames, Top20WritersNums, Top20WritersPoints



def DictOfDicts(Data: pd.DataFrame) -> tuple:
    '''
    接收处理过的DataFrame,生成两个时间轴图像所需要的数据\n
    过程中出现的dic_1是字典的嵌套,详见过程中的注释\n
    :param Data: DataFrame格式的处理过后的总数据
    :return:  返回三个字典,分别是02-15年八个代表性出版社的出版数量和平均评分,\n
    以及各个年份的总出版量(这个数据后续并没有用到,因为八个出版社加起来在总出版量里占比还是很小)
    '''
    dic_1 = {}
    publishers = ['机械工业出版社', '人民邮电出版社', '电子工业出版社',
                  '清华大学出版社', '人民文学出版社', '上海译文出版社',
                  '生活·读书·新知三联书店', '广西师范大学出版社']
    grouped_1 = Data.groupby('time')
    grouped_2 = Data.groupby(['time', 'publisher'])  # 根据两个列——出版年份和出版社——分组
    value = grouped_1.title.count().to_list()  # 各个年份总出版量的列表，只有数据，按照年份从早到晚的顺序
    key = grouped_1.title.count().index.to_list()  # 各个年份的列表
    dic_2 = dict(zip(key, value))  # 生成年份和出版数量对应的字典
    # dic_1是字典的嵌套,第一层:  年份:字典
    #                第二层:   出版社:列表(列表内包含该年该出版社出版的作品数量和平均分)
    for (year, pub), group in tqdm(grouped_2):  # 遍历根据多个列分组的GroupBy对象,(year, pub)是分组的列名的元组,group是这个组里的dataframe
        if year not in dic_1:
            dic_1[year] = {}
        AvgPoints = group.points.mean()
        BookNum = group.title.count()
        dic_1[year][pub] = [AvgPoints, BookNum]

    data_points = {}
    data_nums = {}
    data_all_published = {}
    for year in tqdm(range(2002, 2015)):
        data_points[year] = [dic_1[year][name][0] for name in publishers]
        data_nums[year] = [dic_1[year][name][1] for name in publishers]
        data_all_published[year] = dic_2[year]

    # <class 'numpy.int32'>  data_nums的每一个值是一个列表，列表里的元素是numpy的数据类型，转成python的int类型
    for k in tqdm(data_nums.keys()):
        data_nums[k] = [int(x) for x in data_nums[k]]

    print("Successfully ran DictOfDicts")
    return data_points, data_nums, data_all_published



def RankOfPublisher(Data: pd.DataFrame) -> tuple:
    '''
    出版物数量前10的出版社的评分、数量和价格排名\n
    :param Data: DataFrame
    :return: tuple of five lists
    '''

    NamesOfPubs = Data.groupby('publisher').title.count().sort_values(ascending=False).index.to_list()[:10]
    # ['上海译文出版社', '中信出版社', '人民文学出版社', '生活·读书·新知三联书店', '机械工业出版社', '广西师范大学出版社',
    # '人民邮电出版社', '译林出版社', '新星出版社', '南海出版公司']
    BookNumsOfPubs = Data.groupby('publisher').title.count().sort_values(ascending=False).to_list()[:10]
    AvgPointsOfAll = Data.groupby('publisher').points.mean().to_dict()
    PriceOfAllPubs = Data.groupby('publisher').price.mean()
    AvgPoints = [AvgPointsOfAll[x] for x in NamesOfPubs]
    AvgPrice = [float(PriceOfAllPubs[x]) for x in NamesOfPubs]
    # [28.816419957850353, 45.66259003161226, 33.190557605831515, 46.20738582677161, 53.89634968994886,
    # 48.97546939253989, 63.05241026118068, 34.61701086956516, 43.61881274789915, 33.36948051948049]
    PriceOfAllBooks = [float(x) for x in tqdm(Data.price.to_list())]  # 浮点数列表，包含每一本书的价格

    print("Successfully ran RankOfPublishers")
    return BookNumsOfPubs, NamesOfPubs, AvgPoints, AvgPrice, PriceOfAllBooks



def BarAndLine(Top20WritersNames: list, Top20WritersNums: list, Top20WritersPoints: list):
    '''
    高产作家(productive author)创作数量及其评分\n
    :param Top20WritersNames: 高产作者前20名称的列表
    :param Top20WritersNums: 高产作者前20各自的作品数量的列表
    :param Top20WritersPoints: 高产作者前20的作品评分的列表
    :return: 没有
    '''
    global dir_to_save
    x_data = Top20WritersNames
    bar = (
        Bar(init_opts=opts.InitOpts(width="1400px", height="700px"))  # 指定图片大小
            .add_xaxis(xaxis_data=x_data)
            .add_yaxis(series_name="作品数量", yaxis_data=Top20WritersNums, )
            .extend_axis(
            yaxis=opts.AxisOpts(
                name="平均分",
                type_="value",  # 数值轴。还有“time”、“category”等选项，试了试发现画出来的图很奇怪，不深究了
                min_=0,
                max_=10,
                interval=0.5,
                # axislabel_opts=opts.LabelOpts(formatter="{value}"), y轴刻度需要单位时设置，此时为评价分数，不用单位
            )
        )
            .set_global_opts(
            tooltip_opts=opts.TooltipOpts(
                is_show=True, trigger="axis", axis_pointer_type="cross"
            ),
            xaxis_opts=opts.AxisOpts(
                type_="category",
                axispointer_opts=opts.AxisPointerOpts(is_show=True, type_="shadow"),
                axislabel_opts=opts.LabelOpts(rotate=-30, font_size=18)  # x轴标签旋转，设置字体大小
            ),
            yaxis_opts=opts.AxisOpts(
                name="作品数量",
                type_="value",
                min_=0,
                max_=300,
                interval=50,
                axislabel_opts=opts.LabelOpts(formatter="{value}"),
                axistick_opts=opts.AxisTickOpts(is_show=True),
                splitline_opts=opts.SplitLineOpts(is_show=True),
            ),
            title_opts=opts.TitleOpts(title='高产作家创作数量及其评分'
                                      , pos_left='20%'  # 标题的位置 距离左边20%距离。
                                      , title_textstyle_opts=opts.TextStyleOpts(color='black'
                                                                                , font_size=20
                                                                                , font_weight='bold'
                                                                                )  # 大标题文字的格式配置
                                      )
        )
    )

    line = (
        Line()
            .add_xaxis(xaxis_data=x_data)
            .add_yaxis(
            series_name="平均评分",
            yaxis_index=1,
            y_axis=Top20WritersPoints,
            label_opts=opts.LabelOpts(is_show=False),
        )
    )

    bar.overlap(line).render(dir_to_save + "ProductiveAuthor_bar_and_line.html")
    print("Successfully drew ProductiveAuthor_bar_and_line")



def TimelinePie(data_nums: dict):
    '''
    我自己选的八个出版社的年出版量对比\n
    :param data_nums: 字典,键为年份,值是列表,存放各出版社的出版数量
    :return: 不存在
    '''
    global dir_to_save
    attr = ['机械工业出版社', '人民邮电出版社', '电子工业出版社',
            '清华大学出版社', '人民文学出版社', '上海译文出版社',
            '生活·读书·新知三联书店', '广西师范大学出版社']
    tl = Timeline()
    for i in tqdm(range(2002, 2015)):
        pie = (
            Pie()
                .add(
                "",
                [list(z) for z in zip(attr, data_nums[i])],
                rosetype="radius",
                radius=["30%", "55%"],
            )
                .set_global_opts(title_opts=opts.TitleOpts("8个出版社的{}年出版量对比".format(i),
                                                           pos_top='15%')
                                 )
        )
        tl.add(pie, "{}年".format(i))
    tl.render(dir_to_save + "TypicalPublishers_timeline_pie.html")
    print("Successfully drew TypicalPublishers_timeline_pie")



def TimelineBar(Data: pd.DataFrame):
    '''
    具有代表性的出版社出版数量及评分情况(和另一个时间轴饼图有些重复了,只是多了每年的评分情况)\n
    这张图在文档里应该是饼图和柱状图在一张图上的，但是因为出版数量和评分并非一个数量级，示例中是
    第一二三产业的占比，这是同一单位。所以不画饼图了\n
    但是有一些代码，包括函数名什么的,没有修改\n
    :param Data: 本来这里是直接用main函数里的data_points,data_nums的，但是本函数会修改data_nums和data_points，会影响后续调用，故这里传Data，在本函数内生成这两个变量
    :return: 假装模块化编程，其实只是把代码分类，没有代码复用的功能，连return都没有，太差劲了
    '''
    global dir_to_save
    data_points, data_nums = DictOfDicts(Data)[:2]
    total_data = {}
    name_list = ['机械工业出版社', '人民邮电出版社', '电子工业出版社',
                 '清华大学出版社', '人民文学出版社', '上海译文出版社',
                 '生活·读书·新知三联书店', '广西师范大学出版社']

    def format_data(data: dict) -> dict:
        for year in tqdm(range(2002, 2015)):
            max_data, sum_data = 0, 0
            temp = data[year]
            max_data = max(temp)
            for i in range(len(temp)):
                sum_data += temp[i]
                data[year][i] = {"name": name_list[i], "value": temp[i]}
            data[str(year) + "max"] = int(max_data / 100) * 100
            data[str(year) + "sum"] = sum_data
        return data

    total_data["dataPoints"] = format_data(data=data_points)
    total_data["dataNums"] = format_data(data=data_nums)

    def get_year_overlap_chart(year: int) -> Bar:
        bar = (
            Bar()
                .add_xaxis(xaxis_data=name_list)
                .add_yaxis(
                series_name="NUMS",
                yaxis_data=total_data["dataNums"][year],
                is_selected=True,
                label_opts=opts.LabelOpts(is_show=False),
            )
                .add_yaxis(
                series_name="POINTS",
                yaxis_data=total_data["dataPoints"][year],
                is_selected=True,
                yaxis_index=1,  # NUMS和POINTS两个yaxis数量级不同，故分别控制不同的坐标轴
                label_opts=opts.LabelOpts(is_show=False),
            )
                .extend_axis(
                yaxis=opts.AxisOpts(
                    name="平均评分",
                    type_="value",  # 数值轴。还有“time”、“category”等选项，试了试发现画出来的图很奇怪，不深究了
                    min_=7.5,
                    max_=9,
                    interval=0.2,
                    # axislabel_opts=opts.LabelOpts(formatter="{value}"), y轴刻度需要单位时设置，此时为评价分数，不用单位
                )
            )
                .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="{}代表性出版社出版数量及评分情况".format(year)),
                tooltip_opts=opts.TooltipOpts(
                    is_show=True, trigger="axis", axis_pointer_type="shadow"
                ),
            )
        )
        # 饼图显示效果不好，会和柱状图重叠，而且出版数量和评分并非一个单位，放在一个饼图中没有意义
        # pie = (
        #     Pie()
        #         .add(
        #         series_name="GDP占比",
        #         data_pair=[
        #             ["dataNums", total_data["dataNums"]["{}sum".format(year)]],
        #             ["dataPoints", total_data["dataPoints"]["{}sum".format(year)]],
        #         ],
        #         center=["75%", "35%"],
        #         radius="28%",
        #     )
        #         .set_series_opts(tooltip_opts=opts.TooltipOpts(is_show=True, trigger="item"))
        # )
        return bar

    # 生成时间轴的图
    timeline = Timeline(init_opts=opts.InitOpts(width="1200px", height="600px"))

    for y in range(2002, 2015):
        timeline.add(get_year_overlap_chart(year=y), time_point=str(y))

    # 1.0.0 版本的 add_schema 暂时没有补上 return self 所以只能这么写着
    timeline.add_schema(is_auto_play=True, play_interval=1000)
    timeline.render(dir_to_save + "TypicalPublishers_timeline_bar.html")
    print("Successfully drew TypicalPublishers_timeline_bar")



def RadarChart(BookNumsOfPubs: list, NamesOfPubs: list, AvgPoints: list, AvgPrice: list):
    '''
    出版物数量前10的出版社的数量和评分\n
    :param BookNumsOfPubs: 详见RankOfPublisher()函数
    :param NamesOfPubs: 同上
    :param AvgPoints: 同上
    :param AvgPrice: 同上
    :return: 画图函数，不知道能返回什么
    '''
    global dir_to_save
    AvgPrice = [[x * 80 for x in AvgPrice]]  # 价格放大到原来的80倍
    AvgPoints = [[math.exp(x) for x in tqdm(AvgPoints)]]  # 平均分取指数，放大差异
    BookNumsOfPubs = [[5 * x for x in BookNumsOfPubs]]  # 书籍数量放大5倍,与放大后的评分在同一数量级，便于可视化
    # 以上数据处理方式没有什么理论依据，仅仅是调整到了一个数量级。有关的统计学知识后续学习
    (
        Radar(init_opts=opts.InitOpts(width="1280px", height="720px", bg_color="#CCCCCC"))
            .add_schema(
            schema=[
                opts.RadarIndicatorItem(name=NamesOfPubs[0], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[1], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[2], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[3], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[4], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[5], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[6], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[7], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[8], max_=5500),
                opts.RadarIndicatorItem(name=NamesOfPubs[9], max_=5500),
            ],
            splitarea_opt=opts.SplitAreaOpts(
                is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=1)
            ),
            textstyle_opts=opts.TextStyleOpts(color="#228B22"),
        )
            .add(
            series_name="平均分(取指数后)",
            data=AvgPoints,
            linestyle_opts=opts.LineStyleOpts(color="#D9173B"),
        )
            .add(
            series_name="出版物数量(扩大5倍后)",
            data=BookNumsOfPubs,
            linestyle_opts=opts.LineStyleOpts(color="#0000CD"),
        )
            .add(
            series_name="出版物均价(扩大80倍后)",
            data=AvgPrice,
            linestyle_opts=opts.LineStyleOpts(color="#FFD700"),
        )
            .set_series_opts(label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
            title_opts=opts.TitleOpts(title="出版物数量前10的出版社"), legend_opts=opts.LegendOpts()
        )
            .render(dir_to_save + "Top10PubsInBookNums_radar.html")
    )
    print("Successfully drew Top10PubsInBookNums_radar")



def FunnelSort(PriceOfAllBooks: list):
    '''
    draw一个漏斗picture\n
    :param PriceOfAllBooks: 所有书籍价格的列表，只有价格，没有书籍名！！！
    :return: 么的
    '''
    global dir_to_save
    attr = ['0-20', '20-40', '40-60', '60-80', '80-100', '100-150', '150-∞']  # 指定的价格区间
    BooksOfSpecializedRange = [0 for i in range(7)]  # 用来存放指定价格区间的书籍数量的列表，与上面的attr对应，初始化为0
    for i in PriceOfAllBooks:
        if i <= 20:
            BooksOfSpecializedRange[0] += 1
        elif 20 < i <= 40:
            BooksOfSpecializedRange[1] += 1
        elif 40 < i <= 60:
            BooksOfSpecializedRange[2] += 1
        elif 60 < i <= 80:
            BooksOfSpecializedRange[3] += 1
        elif 80 < i <= 100:
            BooksOfSpecializedRange[4] += 1
        elif 100 < i <= 150:
            BooksOfSpecializedRange[5] += 1
        else:
            BooksOfSpecializedRange[6] += 1

    c = (
        Funnel()
            .add(
            "书籍价格区间",
            [list(z) for z in tqdm(zip(attr, BooksOfSpecializedRange))],
            sort_="ascending",
            label_opts=opts.LabelOpts(position="inside"),
        )
            .set_global_opts(title_opts=opts.TitleOpts(title="不同价格区间的书籍数量",
                                                       pos_top='10%')
                             )
            .render(dir_to_save + "PriceRange_funnel.html")
    )
    print("Successfully drew PriceRange_funnel")


def main():
    # 数据载入、存储、清洗
    ls = MergeFiles()  # 合并文件，读文件，返回列表
    new_ls = DataClean(ls)  # 把格式不正确读不出来数据的行删掉,生成新列表
    Data = GenerateListAndDf(new_ls)  # 生成DataFrame格式的总数据
    print("Data loading and storage cleaning is done successfully")
    # 主要运用groupby方法提取出后续绘图需要的数据内容和格式，其实我也不会什么别的方法
    # 主要是pandas学得太少，面向应用学习知识，没有系统化学习，怎么上手快怎么来
    Top20WritersNames, Top20WritersNums, Top20WritersPoints = RankOfCompositionNums(Data)
    BookNumsOfPubs, NamesOfPubs, AvgPoints, AvgPrice, PriceOfAllBooks = RankOfPublisher(Data)
    data_points, data_nums, data_all_published = DictOfDicts(Data)
    print("All the datas are prepared successfully\nReady to draw")
    # 开始绘图啦！！！装作模块化编程的样子，其实只是简单地把代码放在了不同函数下，没有体现代码复用的思维。
    TimelineBar(Data)
    # 本来这里是直接传data_points, data_nums的,但是TimelineBar函数会修改data_points和nums(可变对象),故传data,在函数里生成points和nums
    # 如果要效率高一点，就把TimelinBar放到TimelinePie后面，仍然传data_points和data_nums
    TimelinePie(data_nums)
    FunnelSort(PriceOfAllBooks)
    BarAndLine(Top20WritersNames, Top20WritersNums, Top20WritersPoints)
    RadarChart(BookNumsOfPubs, NamesOfPubs, AvgPoints, AvgPrice)
    print("All the charts are completed successfully")  # 这个successfully太魔性了

dir_to_save = './Charts/'  # 图片保存路径，在每个绘图函数里声明为全局变量
main()
