# -*- coding: UTF-8 -*-
# Distributed under the terms of GPL version 2 or any later
# Copyright (C) Kristopher Tate/BlueBridge technologies, 2005
# Roster module for xmppd.py

from xmpp import *

class ROSTER(PlugIn):
    NS = NS_ROSTER
    def plugin(self,server):
        server.Dispatcher.RegisterHandler('iq',self.RosterIqHandler,typ='set',ns=NS_ROSTER,xmlns=NS_CLIENT)
        server.Dispatcher.RegisterHandler('iq',self.RosterIqHandler,typ='get',ns=NS_ROSTER,xmlns=NS_CLIENT)

    def RosterAdd(self,session,stanza):
        s_split_jid = session.getSplitJID()
        the_roster = session.getRoster()
        if stanza.getType() == 'set' and stanza.getTag('query').kids != []:
            for kid in stanza.getTag('query').kids:
                split_jid = self._owner.tool_split_jid(kid.getAttr('jid'))
                if split_jid == None: raise NodeProcessed
                if kid.getName() == 'item' and kid.getAttr('subscription') != 'remove':
                    info = {}
                    name = kid.getAttr('name')
                    if name != None: info.update({'name':name})

                    subscription = kid.getAttr('subscription')
                    if subscription != None: info.update({'subscription':subscription})
                    elif kid.getAttr('jid') not in the_roster.keys() or 'subscription' not in the_roster[kid.getAttr('jid')]:
                        self.DEBUG('###ROSTER+: Wow, subscription is not active -- better create one pronto!','warn')
                        kid.setAttr('subscription','none')

                    ask = kid.getAttr('ask')
                    if ask != None:
                        info.update({'ask':ask})
                    elif ask == 'InternalDelete':
                        kid.delAttr('ask')
                        self._owner.DB.del_from_roster_jid(s_split_jid[1],s_split_jid[0],split_jid[0]+'@'+split_jid[1],'ask')

                    self.DEBUG(info,'error')
                    self._owner.DB.save_to_roster(s_split_jid[1],s_split_jid[0],split_jid[0]+'@'+split_jid[1],info)
                    if kid.kids != []:
                        group_list = []
                        for grandkid in kid.kids:
                            if grandkid.getName() == 'group':
                                group_list += [grandkid.getData()]

                        self._owner.DB.save_groupie(s_split_jid[1],s_split_jid[0],split_jid[0]+'@'+split_jid[1],group_list)

    def RosterRemove(self,session,stanza):
        s_split_jid = session.getSplitJID()
        if stanza.getType() == 'set' and stanza.getTag('query').kids != []:
            for kid in stanza.getTag('query').kids:
                if kid.getName() == 'item' and kid.getAttr('subscription') == 'remove':
                    #split_jid = self._owner.tool_split_jid(kid.getAttr('jid'))
                    p = Presence(to=kid.getAttr('jid'),frm=session.getBareJID(),typ='unsubscribe')
                    session.dispatch(p)
                    split_jid = self._owner.tool_split_jid(kid.getAttr('jid'))
                    p = Presence(to=kid.getAttr('jid'),frm=session.getBareJID(),typ='unsubscribed')
                    session.dispatch(p)

                    session.enqueue(stanza)

                    self._owner.DB.del_from_roster(s_split_jid[1],s_split_jid[0],kid.getAttr('jid'))
                    self._owner.DB.del_groupie(s_split_jid[1],s_split_jid[0],kid.getAttr('jid'))

                    #Tell 'em we just road-off into the sunset
                    split_jid = self._owner.tool_split_jid(kid.getAttr('jid'))
                    p = Presence(to=kid.getAttr('jid'),frm=session.peer,typ='unavailable')
                    session.dispatch(p)

    def RosterPushOne(self,session,stanza,mode='set',options=None):
        self.DEBUG('#ROSTER#: Pushing one out!','warn')
        #Stanza Stuff
        to=stanza['to']
        if not to: return # Not for us.
        to_node=to.getNode()
        if not to_node: return # Yep, not for us.
        to_domain=to.getDomain()
        if to_domain in self._owner.servernames:
            bareto=to_node+'@'+to_domain
            to_roster=self._owner.DB.get(to_domain,to_node,'roster')
            """
            <iq type='set'>
              <query xmlns='jabber:iq:roster'>
                <item
                    jid='contact@example.org'
                    subscription='none'
                    ask='subscribe'
                    name='MyContact'>
                  <group>MyBuddies</group>
                </item>
              </query>
            </iq>
            """
            out=Iq(typ=mode)
            out.T.query.setNamespace(NS_ROSTER)
            atag = out.T.query.NT.item
            s_split_jid = session.getSplitJID()
            split_jid = self._owner.tool_split_jid(bareto)
            name = self._owner.DB.get(split_jid[1],split_jid[0],'name')
            groups = session.getGroups()
            atag.setAttr('jid',bareto)
            for x,y in session.getRoster()[bareto].items():
                atag.setAttr(x,y)
            if type(options) == dict and 'attr' in options:
                for ok,od in options['attr']:
                    atag.setAttr(ok,od)
            if atag.getAttr('name') == None and name != None: atag.setAttr('name',name)

            ask = atag.getAttr('ask')
            if ask == 'InternalDelete':
                atag.delAttr('ask')
                self._owner.DB.del_from_roster_jid(s_split_jid[1],s_split_jid[0],bareto,'ask')

            if groups != None:
                for gn,gm in groups.items():
                    if bareto in gm:
                        atag.T.group.setData(gn)
                        break
            else:
                atag.T.group.setData('My Friends')
            barejid = session.getBareJID()
            for resource in self._owner.Router._data[barejid].keys():
                s=self._owner.getsession(barejid+'/'+resource)
                s.send(out)
        self.DEBUG('#ROSTER#: Pushing one out! [COMPLETE]','warn')

    def RosterPush(self,session,stanza,mode='result'):
        rep=stanza.buildReply(mode)
        for k,v in session.getRoster().items():
            atag = rep.T.query.NT.item
            split_jid = self._owner.tool_split_jid(k)
            if split_jid != None:
                name = self._owner.DB.get(split_jid[1],split_jid[0],'name')
            else:
                name = None
            groups = session.getGroups()
            atag.setAttr('jid',k)
            for x,y in v.items():
                atag.setAttr(x,y)
            if atag.getAttr('name') == None and name != None: atag.setAttr('name',name)

            if groups != None:
                for gn,gm in groups.items():
                    for igm in gm:
                        if igm == k:
                            atag.T.group.setData(gn)
                            break
            else:
                atag.T.group.setData('My Friends')
        session.send(rep)

    def RosterIqHandler(self,session,stanza):
        #print("session info:", dir(session))
        s_split_jid = self._owner.tool_split_jid(session.peer)
        if stanza.getType() == 'set' and stanza.getTag('query').kids != []:
            for kid in stanza.getTag('query').kids:
                split_jid = self._owner.tool_split_jid(kid.getAttr('jid'))
                if kid.getName() == 'item' and kid.getAttr('subscription') != 'remove':
                    self.RosterAdd(session,stanza)
                elif kid.getName() == 'item' and kid.getAttr('subscription') == 'remove':
                    self.RosterRemove(session,stanza)
            self.RosterPush(session,stanza,'set') #Push it out, will ya?
            IQ = Iq(typ='result',to=session.peer)
            IQ.setAttr('id',stanza.getID())
            session.send(IQ)
        elif stanza.getType() == 'get' and stanza.getTag('query').kids == []:
            self.RosterPush(session,stanza,'result') #How's the result???

        raise NodeProcessed
