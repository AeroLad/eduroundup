from pygooglenews import GoogleNews
from newspaper import Article, Config
import datetime, json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import time, random, dateparser
import nltk
from database_models import Article as DBArticle
from wordpress_xmlrpc import Client as WPClient, WordPressPost as WPPost
from wordpress_xmlrpc.methods.posts import NewPost, GetPost
from transformers import pipeline


objSummarizer   = pipeline("summarization")
strUserAgent    = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
objConfig       = Config()
objConfig.browser_user_agent = strUserAgent

objEngine       = create_engine('',echo=False)
objSession      = sessionmaker(bind=objEngine)()
objToday        = datetime.date.today()
objYesterday    = objToday - datetime.timedelta(days=2)
strToday        = objToday.strftime("%Y-%m-%d")
strYesterday    = objYesterday.strftime("%Y-%m-%d")

proxyDict = None

objWPClient     = WPClient()

print("Obtaining news")
objGnews        = GoogleNews(lang='en',country='pk')
objSearch       = objGnews.search('education school university pakistan',proxies=proxyDict,from_=strYesterday,to_=strToday)

arrResults      = objSearch['entries']

for dictResult in arrResults:
    dictResult['published'] = dateparser.parse(dictResult['published']).date()
print("Obtained news: {0} items".format(len(arrResults)))


arrKeywords = [
    "school",
    "education",
    "school",
    "university",
    "class",
    "grade",
    "kindergarten",
    "student",
    "institute"
]

arrArticles = []
for intIndex,dictResult in enumerate(arrResults):
    print("Article: {0} / {1}".format(intIndex+1,len(arrResults)))

    strTitle                = dictResult['title'].strip()
    strSummary              = dictResult['summary'].strip()
    strMerge                = (strTitle + strSummary).lower()
    dtDate                  = dictResult['published']
    strURL                  = dictResult['link']
    strSource               = dictResult.get('source',{}).get('title','').strip()

    bShouldParse = False
    for strKeyword in arrKeywords:
        if strKeyword in strMerge:
            bShouldParse = True
            break
    if bShouldParse == False: continue

    intDBQuery              = objSession.query(DBArticle).filter_by(title=strTitle,date=dtDate).count()
    if intDBQuery > 0: continue

    dictDBArticle           = {
        "title"     : strTitle,
        "date"      : dtDate,
        "source"    : strSource,
        "url"       : strURL
    }
    objDBArticle            = DBArticle(**dictDBArticle)
    objSession.add(objDBArticle)
    objSession.commit()

    try:
        dictArticle = {}
        objArticle  = Article(strURL)
        objArticle.download()
        objArticle.parse()
        objArticle.nlp()

        strTitle                = objArticle.title
        strText                 = objArticle.text
        strSummary              = objArticle.summary

        arrSourceVariations     = ["({})".format(strSource), strSource]
        for strSourceVar in arrSourceVariations:
            if strSourceVar in strText: strText = strText.replace(strSourceVar,'').strip()
            if strSourceVar in strSummary: strSummary = strSummary.replace(strSourceVar,'').strip()
            if strSourceVar in strTitle: strTitle = strTitle.replace(strSourceVar,'').strip()


        dictArticle['title']    = strTitle
        dictArticle['date']     = dtDate
        dictArticle['text']     = strText
        dictArticle['summary']  = strSummary
        dictArticle['source']   = strSource
        dictArticle['link']     = strURL

        strMerge                = strTitle + " " + strText
        intMinLength            = int(0.8*len(strMerge.split()))
        strText                 = objSummarizer(strMerge,min_length=intMinLength)

        # arrArticles.append(dictArticle)
        objWPPost               = WPPost()
        objWPPost.title         = strTitle
        objWPPost.content       = strText + "\nSource: <a href=\"{0}\" target=\"_blank\" rel=\"noopener noreferrer\">{1}</a>".format(strURL,strSource)
        objWPPost.terms_names   = {
            'category' : ['News']
        }
        objWPClient.call(NewPost(objWPPost))
    except Exception as e:
        print(str(e))

    time.sleep(random.uniform(10,12))