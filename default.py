# -*- coding: utf-8 -*-
#myChannels XBMC Addon

import sys
import httplib

import urllib, urllib2, cookielib, datetime, time, re, os, string, math
import xbmcplugin, xbmcgui, xbmcaddon, xbmcvfs, xbmc
import cgi, gzip
import json
from StringIO import StringIO
from datetime import timedelta
import calendar
from threading import Timer
from urlparse import urlparse
from urlparse import parse_qsl
import base64


#USER_AGENT = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3'
USER_AGENT = 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.143 Safari/537.36'
GENRE      = "Video"
UTF8          = 'utf-8'
RE_HHEAD    = re.compile('<li class="firstcol">.+?href="(.+?)"')
RE_STREAMER = re.compile('flashplayer: "(.+?)".+?streamer: "(.+?)".+?file: "(.+?)\.flv"')
RE_TOKEN    = re.compile('getJSON.+?"(.+?)"')
RE_MAKE1    = re.compile('x\("(.+?)"')
RE_MAKE2    = re.compile('unescape\("(.+?)"')
RE_MAKE3    = re.compile('c="(.+?)"')
RE_MAKE4    = re.compile('Array\((.+?)\)')

addon         = xbmcaddon.Addon('script.CANChannels')
__addonname__ = 'script.CANChannels'
__language__  = addon.getLocalizedString


home          = addon.getAddonInfo('path').decode(UTF8)
icon          = xbmc.translatePath(os.path.join(home, 'icon.png'))
addonfanart   = xbmc.translatePath(os.path.join(home, 'fanart.jpg'))
epgfile       = xbmc.translatePath(os.path.join(home, 'epg.txt'))
tbarfile      = xbmc.translatePath(os.path.join(home, 'timebar.png'))
background    = xbmc.translatePath(os.path.join(home, 'background.jpg'))


def log(txt):
    message = '%s: %s' % (__addonname__, txt.encode('ascii', 'ignore'))
    xbmc.log(msg=message, level=xbmc.LOGDEBUG)

def deuni(a):
    a = a.replace('&amp;#039;',"'")
    a = a.replace('&amp','&')
    a = a.replace('&;','&')
    a = a.replace('&quot;',"'")
    a = a.replace('&#039;',"'")
    a = a.replace('&#39;',"'")
    return a


USER_AGENT    = 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.93 Safari/537.36'
defaultHeaders = {'User-Agent':USER_AGENT, 
                 'Accept':"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", 
                 'Accept-Encoding':'gzip,deflate,sdch',
                 'Accept-Language':'en-US,en;q=0.8'} 

def getRequest(url, user_data=None, headers = defaultHeaders , alert=True):

              log("getRequest URL:"+str(url))
              if addon.getSetting('us_proxy_enable') == 'true':
                  us_proxy = 'http://%s:%s' % (addon.getSetting('us_proxy'), addon.getSetting('us_proxy_port'))
                  proxy_handler = urllib2.ProxyHandler({'http':us_proxy})
                  if addon.getSetting('us_proxy_pass') <> '' and addon.getSetting('us_proxy_user') <> '':
                      log('Using authenticated proxy: ' + us_proxy)
                      password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
                      password_mgr.add_password(None, us_proxy, addon.getSetting('us_proxy_user'), addon.getSetting('us_proxy_pass'))
                      proxy_auth_handler = urllib2.ProxyBasicAuthHandler(password_mgr)
                      opener = urllib2.build_opener(proxy_handler, proxy_auth_handler)
                  else:
                      log('Using proxy: ' + us_proxy)
                      opener = urllib2.build_opener(proxy_handler)
              else:   
                  opener = urllib2.build_opener()
              urllib2.install_opener(opener)

              log("getRequest URL:"+str(url))
              req = urllib2.Request(url.encode(UTF8), user_data, headers)

              try:
                 response = urllib2.urlopen(req)
                 if response.info().getheader('Content-Encoding') == 'gzip':
                    log("Content Encoding == gzip")
                    buf = StringIO( response.read())
                    f = gzip.GzipFile(fileobj=buf)
                    link1 = f.read()
                 else:
                    link1=response.read()

              except urllib2.URLError, e:
                 if alert:
                     xbmc.executebuiltin('XBMC.Notification("%s", "%s", %s)' % ( __addonname__, e , 10000) )
                 link1 = ""

              if not (str(url).endswith('.zip')):
                 link1 = str(link1).replace('\n','')
              return(link1)


screen_width = 1366
screenHeight = 768
row_height   = 55
logo_width   = 55
cname_width  = 100
poffset      = logo_width+cname_width
progs_width  = float(screen_width - poffset)
MAXIMUMROW   = 8

 
#get actioncodes from https://github.com/xbmc/xbmc/blob/master/xbmc/guilib/Key.h
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK      = 92
ACTION_PAGE_UP       = 5
ACTION_PAGE_DOWN     = 6
ACTION_MOVE_LEFT     = 1
ACTION_MOVE_RIGHT    = 2 
ACTION_MOVE_UP       = 3
ACTION_MOVE_DOWN     = 4
ACTION_MOUSE_MOVE    = 107

class MyClass(xbmcgui.Window):

  def __init__(self):

    progress = xbmcgui.DialogProgress()
    progress.create(__addonname__, 'Initializing')


    jf = open(epgfile)
    pm = json.load(jf)
    jf.close()

    self.chans=[]
    progress_pct = int(100 / len(pm['epgs']))
    progress_abs = 0
    for epg in pm['epgs']:
      epg['Name'] = epg['Name']
      progress.update(progress_abs, __addonname__, "Loading EPG : %s" % epg['Name'])
      progress_abs += progress_pct
      urls   = epg['urls']
      epgUrl = '%s&tz=%s' % (epg['epgUrl'], __language__(int(addon.getSetting('tz'))+30010).replace('/','%2F'))


      html = getRequest(epgUrl)
      sch = json.loads(html)
      self.dtimes  = sch['data']['displayTime']

      achannels = sch['data']['results']['stations']
      for channel in achannels:
        for u in urls.keys():
            try:
             if u == channel['callSign']:
               channel['url']=urls[u]
               self.chans.append(channel)
               break
            except:
               break

    self.ctlList = []
    self.buttonList=[]

    self.ctlList.append(xbmcgui.ControlImage(0,0,screen_width,screenHeight,background))

    self.current_page = 0
    self.rowsize = 0
    self.startPos= 260


    toffset = 0
    twidth = int(progs_width/len(self.dtimes))
    for dtime in self.dtimes:
      self.ctlList.append(xbmcgui.ControlLabel(poffset+toffset, self.startPos-28, twidth, row_height, str(dtime)))
      toffset += twidth


    self.player=xbmc.Player()
    self.button = []

    self.current_plot = xbmcgui.ControlTextBox(int(screen_width/2), 0+10, int(screen_width/2)-100, self.startPos - 10)
    self.ctlList.append(self.current_plot)
    self.dummyButton = xbmcgui.ControlButton(2000,2000,0,0,None) # create a dummy off the screen for ACTION_MOVE_DOWN
    self.ctlList.append(self.dummyButton)
    self.timeBar = xbmcgui.ControlTextBox(0,0,300,55)
    self.ctlList.append(self.timeBar)
    self.addControls(self.ctlList)

    self.topRow = False
    self.bottomRow = False
    self.show_epg(self.chans, self.current_page)
    progress.close()

    self.tbarctl = xbmcgui.ControlImage(poffset + (int(progs_width/ (3*60))*datetime.datetime.now().minute), self.startPos ,
                                         3,screenHeight-self.startPos,tbarfile)
    self.addControl(self.tbarctl)
    self.currentHour = datetime.datetime.now().hour
    t = Timer(1, self.updateTimeBar)
    self.time_slept = 60-1
    t.start()


  def updateTimeBar(self):
   self.time_slept = self.time_slept + 1
   if self.time_slept >= 60:
    self.time_slept = 0
    try:
      xpos = self.tbarctl.getX()
      xpos = xpos + int(progs_width/ (3*60))
      ypos = self.tbarctl.getY()
      self.tbarctl.setPosition(xpos, ypos)
    except: pass

    self.timeBar.reset()
    self.timeBar.setText(datetime.datetime.now().strftime('%a %b %d, %Y  %I:%M %p'))

   if not xbmc.abortRequested:
     t = Timer(1, self.updateTimeBar)
     t.start()


  def show_epg(self, channels, page_no):
    self.last_page = False
    self.removeControls(self.buttonList)
    self.buttonList=[]

    self.button = [] #added
    self.pdata = [] #added
    

    row = 0
    for channel in channels[page_no*8:page_no*8+8]:
         self.button.append([]) #added
         self.pdata.append([]) #added
         self.pdata[row].append([]) #added
         self.pdata[row][0]={} #added
         self.pdata[row][0]['url']   = channel['url']
         self.pdata[row][0]['cname'] = xbmcgui.ControlLabel(0, self.startPos+17+(row*row_height), 100, row_height,channel['callSign'])
         self.pdata[row][0]['cicon']  = channel['thumbnail'].replace('\\','')
         self.pdata[row][0]['cimage'] = xbmcgui.ControlImage(100, self.startPos+(row*row_height), logo_width, logo_width,self.pdata[row][0]['cicon'])
         self.buttonList.append(self.pdata[row][0]['cimage'])
         self.buttonList.append(self.pdata[row][0]['cname'])


         events = channel['events']
         col = 0
         coffset = 0
         for event in events:
           if col != 0:  #added
              self.pdata[row].append([]) #added
              self.pdata[row][col]={}#added
           try:
             self.pdata[row][col]['desc'] = '%s - %s\n%s' % (event['startTimeDisplay'],
                                                          event['endTimeDisplay'],
                                                      str(event['program']['description']))
           except:
             self.pdata[row][col]['desc'] = ""
           self.pdata[row][col]['duration'] = str(event['duration'])
           self.pdata[row][col]['eptitle'] = '%s - %s : %s' % (event['startTimeDisplay'],
                                                                 event['endTimeDisplay'],
                                                                 event['eptitle'])

           cwidth = int((float(event['percentWidth'])/100)*progs_width)
           self.button[row].append([])#added
           self.button[row][col]=xbmcgui.ControlButton(poffset+coffset, self.startPos+(row*row_height), cwidth, row_height, event['program']['title'])

           self.buttonList.append(self.button[row][col])
           coffset = coffset + cwidth
           col = col + 1
         row =  row +1
         
         if row == MAXIMUMROW:
           break

    self.rowsize = row
    self.addControls(self.buttonList)


    if row == 0:
       self.current_page=0
       show_epg(channels, 0) # hack to display first page after last page - could be problem for empty epg
       return
 
    elif row < MAXIMUMROW:
       self.last_page=True


    for row in range(self.rowsize):
          for col in range(len(self.button[row])): # added
              if row < len(self.button)-1:
                 self.button[row][col].controlDown(self.button[row+1][0])
              if col > 0:
                 self.button[row][col].controlLeft(self.button[row][col-1])
                 self.button[row][col-1].controlRight(self.button[row][col])
              if row > 0:
                 self.button[row][col].controlUp(self.button[row-1][0])


    self.topRow = True
    self.bottomRow = False
    control = self.button[0][0]
    self.setFocus(control)
    self.updateEpg(control)
 
  def onAction(self, action):
   if action.getId() in [ACTION_PREVIOUS_MENU, ACTION_PAGE_UP, ACTION_MOVE_UP, ACTION_PAGE_DOWN, ACTION_MOVE_DOWN, 
                         ACTION_MOVE_RIGHT, ACTION_MOVE_LEFT, ACTION_MOUSE_MOVE, ACTION_NAV_BACK]:
    if action in [ACTION_PREVIOUS_MENU, ACTION_NAV_BACK]:
      self.close()
      return
    elif (action == ACTION_PAGE_UP) or ((action == ACTION_MOVE_UP) and (self.topRow == True)) :
      if self.current_page >0:
         self.current_page -= 1 
         self.show_epg(self.chans, self.current_page)
         return
      else:
         self.setFocus(self.button[0][0])
  
    elif (action == ACTION_PAGE_DOWN) or ((action == ACTION_MOVE_DOWN) and (self.bottomRow == True)) :
        if self.last_page:
           self.current_page = 0
        else:
           self.current_page += 1
        self.show_epg(self.chans, self.current_page)
        return

    try:
      control = self.getFocus()
    except:
      control = self.button[0][0]

    self.updateEpg(control)



  def updateEpg(self, control):
   if control != 0:
     for row in range(self.rowsize): # changed from 8
      for col in range(len(self.button[row])): # added in updateEPG

       if control == self.button[row][col]:
        name = control.getLabel()
        plot = self.pdata[row][col]['desc']
        self.current_plot.reset()
        self.current_plot.setText( '%s\n%s' % (name, plot) )
        if row == 0:
            self.topRow = True
            self.bottomRow = False
        elif row == 7:
            self.topRow = False
            self.bottomRow = True
        else:
            self.topRow = False
            self.bottomRow = False


 
  def onControl(self, control):
   for row in range(8): # changed from 8
    for col in range(len(self.button[row])): # added

     if control == self.button[row][col]:
      xpos = self.tbarctl.getX()
      for col in range(len(self.button[row])): # added
       if (self.button[row][col] != 0): 
        x = self.button[row][col].getX()
        if (x <= xpos) and ( x+self.button[row][col].getWidth() >= xpos):
         name     = self.button[row][col].getLabel()
         plot     = self.pdata[row][col]['desc']
         duration = self.pdata[row][col]['duration']
         eptitle  = self.pdata[row][col]['eptitle']
         listitem = xbmcgui.ListItem(name, thumbnailImage=self.pdata[row][0]['cicon'])
         listitem.setInfo('video', {'Title': name, 'Plot': plot, 'Duration': duration, 'Genre': eptitle })

         try:
           url = self.pdata[row][0]['url']
           if url.startswith('theplatform:'):
              url  = url.split(':',1)[1]
              html = getRequest(url)
              try:
                url  = re.compile('<video src="(.+?)"').search(html).group(1)
              except:
                url  = re.compile('<ref src="(.+?)"').search(html).group(1)
           xbmc.Player(xbmc.PLAYER_CORE_AUTO).play(url, listitem)
           return
         except:
           log("MyChannels error parsing play url")
           return


 
# Start of Module
try:
     mydisplay = MyClass()
     mydisplay .doModal()
     del mydisplay
except:
     pass

