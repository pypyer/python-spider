# coding=utf-8
import requests
import json
import re
import sys
import time
from pymongo import MongoClient
import xlrd
# url = "http://xueqiu.com/statuses/search.json?count=10&comment=0&symbol=SZ002161&hl=0&source=user&sort=time&page=1"
userAgent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
HEADERS = {
    'User-Agent': userAgent
}
COUNT = 20
URL = 'http://xueqiu.com/statuses/search.json?'
# class timeoutException(Exception):

def timestamp_datetime(value):
    format = '%Y%m%d %H%M%S'
    # value为传入的值为时间戳(整形)，如：1332888820
    value = time.localtime(value)
    # 最后再经过strftime函数转换为正常日期格式。
    dt = time.strftime(format, value)
    return dt      
class Myrequests(object):
    """docstring for requests"""
    def __init__(self):
        url = 'http://xueqiu.com/'
        s = requests.Session()
        r = s.get(url,headers = HEADERS)
        #s 中含有cookie
        self.s = s
    # @staticmethod
    def get(self,url,timeout,headers,params=None,retry=10):
        for i in xrange(retry):
            r = self.s.get(url,timeout=timeout,headers = headers,params = params)
            if r.status_code == 200:
                return r
            

    def post(self,url,timeout,headers,params=None,retry=10):
        for i in xrange(retry):
            r = self.s.post(url,timeout=timeout,headers = headers,params = params)
            if r.status_code == 200:
                return r
            

myrequests = Myrequests()

class DiscussJsonGetter(object):
    """docstring for DiscussJsonGetter"""
    def __init__(self,stockId):
        self.stockId = stockId
    #拼接完整的json链接
    def urlParam(self,count,symbol,page):
        param = {}
        param['count'] = str(count)
        param['comment'] = '0'
        param['symbol'] = str(symbol)
        param['source'] = 'user'
        param['sort'] = 'time'
        param['page'] = str(page)
        return param

    #通过上面拼接好的链接获取新闻json
    def getDiscussHtml(self,page):
        param = self.urlParam(COUNT,self.stockId,page = page)
        
        r = myrequests.get(URL,timeout= 6,headers=HEADERS,params = param)
        html = r.content
        return html


    def cnonvertHtmlToJson(self,page):
        html = self.getDiscussHtml(page = page)
        html_json = json.loads(html)
        return html_json
            


class CommentJsonGetter(object):
    """docstring for CommentJsonGetter"""
    def __init__(self, discussId):
        self.discussId = str(discussId)

    def getUrl(self):
        url = 'http://xueqiu.com/service/comments?id='+self.discussId+''
        return url

    def getCommentHtml(self):
        url = self.getUrl()
        r = myrequests.post(url,timeout= 6,headers=HEADERS)
        html = r.content
        return html
        

    def cnonvertHtmlToJson(self):
        html = self.getCommentHtml()
        html_json = json.loads(html)
        return html_json


def progressBar(stockId,progress_index,total):
    progress = float(progress_index)/total
    percent = round(progress*100,1)
    # print percent
    sys.stdout.write("%s:[%s%s] %s%% \r"%(stockId,'#'*(int(50*progress)),'-'*(50-int(50*progress)),str(percent)))
    sys.stdout.flush()


class ExtractData(object):
    """docstring for extractDataFromJson"""
    def __init__(self,stockId):
        self.stockId = stockId
        self.d = DiscussJsonGetter(stockId)

    def getMaxPage(self):
        return self.d.cnonvertHtmlToJson(page = 1)['maxPage']

    def updateTotal(self,listLengthInPage,total):
        if listLengthInPage != 20:
            total = total-(20-listLengthInPage)
        return total

    def getOneComment(self,item):
        comment = item['text']
        pattern = re.compile(r'<img.*?alt="\[(.*?)\]".*?>')
        img = pattern.findall(comment)
        face = []
        if img:
            for feel in img:
                face.append(feel)
        pattern = re.compile(r'<.*?>')
        comment = pattern.sub('',comment)
        usr = item['user']['screen_name']
        replyTo =  item['reply_screenName']
        comment_dict = {"text":comment,"usr":usr}
        if replyTo:
            comment_dict.update({"replyTo":replyTo})
        if img:
            comment_dict.update({"img":face})
        return comment_dict

    def getAllComment(self,discussId):
        c = CommentJsonGetter(discussId)
        comment_json = c.cnonvertHtmlToJson()
        comment_list=[]
        for i in xrange(len(comment_json['comments'])):
            item = comment_json['comments'][i]
            comment_dict = self.getOneComment(item)
            comment_list.append(comment_dict)
        return comment_list

    def extractDataFromOneDiscussion(self,item):
        text = item['text']
        time = item['created_at']
        formateTime = timestamp_datetime(long(str(time)[0:10]))
        pattern = re.compile(r'<img.*?alt="\[(.*?)\]".*?>')
        img = pattern.findall(text)
        face = []
        if img:
            for feel in img:
                face.append(feel)
        pattern = re.compile(r'<.*?>')
        text = pattern.sub('',text)
        screen_name = item['user']['screen_name']
        qout = item['retweeted_status']
        if qout:
            qout_usr = qout["user"]["screen_name"]
            qout_discuss = pattern.sub('',qout["text"])
            qout = {"usr":qout_usr,"discuss":qout_discuss}
        comment_list=[]
        replyCount = item['reply_count']
        if replyCount>0:
            discussId = item['id']
            try:
                comment_list = self.getAllComment(discussId)
            except Exception,e:
                print "\nCommentJson Exception %s"%e
                comment_list = []
        return (text,formateTime,face,screen_name,qout,comment_list)

    def extractDataFromJson(self):
        #初始化dict
        discuss_dict = {"symbol":self.stockId}
        discuss_dict["list"] = []
        try:
            maxPage = self.getMaxPage()
        except Exception,e:
            print "\n%s no max page %s"%(self.stockId,e)
            return discuss_dict
        total = maxPage*COUNT
        progress_index = 0

        for page in xrange(1,maxPage+1):
            try:
                discuss_json = self.d.cnonvertHtmlToJson(page)
            except Exception,e:
                print "\nDiscussJson Exception %s"%e
                continue
            listLengthInPage = len(discuss_json['list'])
            total = self.updateTotal(listLengthInPage,total)
            for index in xrange(listLengthInPage):
                item = discuss_json['list'][index]
                text,\
                time,\
                face,\
                usr,\
                qout,\
                comment = self.extractDataFromOneDiscussion(item)
                discuss_dict["list"].append({"text": text,"time":time,"usr":usr})
                if qout:
                    discuss_dict["list"][progress_index].update({"qout":qout})
                if face:
                    discuss_dict["list"][progress_index].update({"img":face})
                if comment:
                    discuss_dict["list"][progress_index].update({"comment":comment})
                progress_index = progress_index+1
                progressBar(self.stockId,progress_index,total)
        return discuss_dict

#读stock表格
def readXls(again = False):
    # Open the workbook
    xl_workbook = xlrd.open_workbook("test.xls")
    sheet_names = xl_workbook.sheet_names()
    xl_sheet = xl_workbook.sheet_by_name(sheet_names[0])
    nrows = xl_sheet.nrows
    ncols = xl_sheet.ncols
    stockid_list = []
    #提取第一列ID
    for cell_obj in xl_sheet.col(0):
        stockid_list.append(cell_obj.value)
    #删除前两行
    del stockid_list[0:2]
    #提取第三列辨别深圳还是上海
    code = []
    for cell_obj in xl_sheet.col(2):
        if u"深圳" in cell_obj.value or u"上海A6" in cell_obj.value:
            code.append('SZ')
        elif u"上海" in cell_obj.value:
            code.append('SH')
        # if u"深圳A" in cell_obj.value:
        #     code.append('SZ')
        # elif u"上海A" in cell_obj.value:
        #     code.append('SH')
    stockid_list = [''.join(item) for item in zip(code,stockid_list)]
    return stockid_list

# stockList = readXls()
# stockList = ['SZ002163','SZ000689','SZ002758','SZ000922','SZ002386','SH600893','SH600296','SH603006','SZ002363']
discuss_list = []
stockList = ['SZ000922']

for i in stockList:
    e = ExtractData(i)
    discuss_dict = e.extractDataFromJson()
    discuss_list.append(discuss_dict)
    print '\n'

def DBwrite(discuss_list):
    client = MongoClient('localhost', 27017)
    db = client['taolun']
    collection = db['withtime']
    result = collection.insert(discuss_list)

DBwrite(discuss_list)
