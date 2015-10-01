# setenv LD_LIBRARY_PATH ${LD_LIBRARY_PATH}:/media/ShipSoft/genfit-build/lib
inputFile = 'ship.Pythia8-TGeant4.root'
geoFile   = None
debug = False
EcalDebugDraw = False
withNoStrawSmearing = None # True   for debugging purposes
nEvents    = 999999
firstEvent = 0
withHists = True
vertexing = True
dy  = None
saveDisk  = False # remove input file
pidProton = False # if true, take truth, if False fake with pion mass
realPR = ''

import ROOT,os,sys,getopt
import __builtin__ as builtin
from pythia8_conf import addHNLtoROOT
import rootUtils as ut

# init fitter, to be done before importing shipPatRec
#fitter          = ROOT.genfit.KalmanFitter()
#fitter          = ROOT.genfit.KalmanFitterRefTrack()
fitter           = ROOT.genfit.DAF()
import shipPatRec 
#set to True if "real" pattern recognition is required also

if debug == True: shipPatRec.debug = 1

try:
        opts, args = getopt.getopt(sys.argv[1:], "o:D:FHPu:n:f:g:c:hqv:sl:A:Y:i:",\
           ["ecalDebugDraw","inputFile=","geoFile=","nEvents=","noStrawSmearing","noVertexing","saveDisk","realPR"])
except getopt.GetoptError:
        # print help information and exit:
        print ' enter --inputFile=  --geoFile= --nEvents=  --firstEvent=,' 
        print ' noStrawSmearing: no smearing of distance to wire, default on' 
        print ' outputfile will have same name with _rec added'   
        sys.exit()
for o, a in opts:
        if o in ("noVertexing"):
            vertexing = False
        if o in ("noStrawSmearing"):
            withNoStrawSmearing = True
        if o in ("-f", "--inputFile"):
            inputFile = a
        if o in ("-g", "--geoFile"):
            geoFile = a
        if o in ("-n", "--nEvents="):
            nEvents = int(a)
        if o in ("-Y"): 
            dy = float(a)
        if o in ("--ecalDebugDraw"):
            EcalDebugDraw = True
        if o in ("--saveDisk"):
            saveDisk = True
	if o in ("--realPR"):
            realPR = "_PR"
if EcalDebugDraw: ROOT.gSystem.Load("libASImage")

# need to figure out which geometry was used
if not dy:
  # try to extract from input file name
  tmp = inputFile.split('.')
  try:
    dy = float( tmp[1]+'.'+tmp[2] )
  except:
    dy = None
print 'configured to process ',nEvents,' events from ' ,inputFile, \
      ' starting with event ',firstEvent, ' with option Yheight = ',dy,' with vertexing',vertexing,' and real pattern reco',realPR=="_PR"
if not inputFile.find('_rec.root') < 0: 
  outFile   = inputFile
  inputFile = outFile.replace('_rec.root','.root') 
else:
  outFile = inputFile.replace('.root','_rec.root') 
# outfile should be in local directory
  tmp = outFile.split('/')
  outFile = tmp[len(tmp)-1]
  if saveDisk: os.system('mv '+inputFile+' '+outFile)
  else :       os.system('cp '+inputFile+' '+outFile)

if not geoFile:
 tmp = inputFile.replace('ship.','geofile_full.')
 geoFile = tmp.replace('_rec','')
# try to figure out which ecal geo to load
fgeo = ROOT.TFile(geoFile)
sGeo = fgeo.FAIRGeom
if sGeo.GetVolume('EcalModule3') :  ecalGeoFile = "ecal_ellipse6x12m2.geo"
else: ecalGeoFile = "ecal_ellipse5x10m2.geo" 
print 'found ecal geo for ',ecalGeoFile

if withHists:
 h={}
 ut.bookHist(h,'distu','distance to wire',100,0.,5.)
 ut.bookHist(h,'distv','distance to wire',100,0.,5.)
 ut.bookHist(h,'disty','distance to wire',100,0.,5.)
 ut.bookHist(h,'nmeas','nr measuerements',100,0.,50.)
 ut.bookHist(h,'chi2','Chi2/DOF',100,0.,20.)
 ut.bookHist(h,'Vzpull','Vz pull',100,-3.,3.)
 ut.bookHist(h,'Vxpull','Vx pull',100,-3.,3.)
 ut.bookHist(h,'Vypull','Vy pull',100,-3.,3.)

#-----prepare python exit-----------------------------------------------
def pyExit():
 global fitter
 del fitter
 print "finishing pyExit" 
import atexit
atexit.register(pyExit)

from array import array
import shipunit as u
import rootUtils as ut
from ShipGeoConfig import ConfigRegistry
if dy: 
 ShipGeo = ConfigRegistry.loadpy("$FAIRSHIP/geometry/geometry_config.py", Yheight = dy, EcalGeoFile = ecalGeoFile )
else:
 ShipGeo = ConfigRegistry.loadpy("$FAIRSHIP/geometry/geometry_config.py", EcalGeoFile = ecalGeoFile )
# -----Create geometry----------------------------------------------
import shipDet_conf
run = ROOT.FairRunSim()
modules = shipDet_conf.configure(run,ShipGeo)
builtin.debug    = debug
builtin.fitter   = fitter
builtin.ship_geo = ShipGeo # for shipPatRec
addHNLtoROOT()

def myVertex(t1,t2,PosDir):
 # closest distance between two tracks
    # d = |pq . u x v|/|u x v|
   a,u = PosDir[t1]['position'],PosDir[t1]['direction']
   c,v = PosDir[t2]['position'],PosDir[t2]['direction']
   pq = a-c
   uCrossv = u.Cross(v)
   dist  = pq.Dot(uCrossv)/(uCrossv.Mag()+1E-8)
   # u.a - u.c + s*|u|**2 - u.v*t    = 0
   # v.a - v.c + s*v.u    - t*|v|**2 = 0
   E = u.Dot(a) - u.Dot(c) 
   F = v.Dot(a) - v.Dot(c) 
   A,B = u.Mag2(), -u.Dot(v) 
   C,D = u.Dot(v), -v.Mag2()
   t = -(C*E-A*F)/(B*C-A*D)
   X = c.x()+v.x()*t
   Y = c.y()+v.y()*t
   Z = c.z()+v.z()*t
   # sT = ROOT.gROOT.FindAnything('cbmsim')
   #print 'test2 ',X,Y,Z,dist
   return X,Y,Z,abs(dist)

def myVertexError(t1,t2,PosDir,CovMat=None,scalFac=None):
   a,u = PosDir[t1]['position'],PosDir[t1]['direction']
   c,v = PosDir[t2]['position'],PosDir[t2]['direction']
   denom = u.Dot(u)*v.Dot(v)-(u.Dot(v))**2
   tmp1 = c-a
   tmp2 = v.Dot(v)*u-u.Dot(v)*v
   Va = tmp1.Dot(tmp2)/denom
   tmp2 = u.Dot(v)*u-u.Dot(u)*v
   Vb = tmp1.Dot(tmp2)/denom
   X = (a+Va*u+c+Vb*v) * 0.5
   l1 = a - X + u*Va # l2 = c - X + v*Vb
   dist = 2.*ROOT.TMath.Sqrt( l1.Dot(l1) )
   check=c+Vb*v
   if not CovMat: return X,dist
   T = ROOT.TMatrixD(3,12)
   for i in range(3):
     for k in range(4):
       for j in range(3): 
        KD = 0
        if i==j: KD = 1
        if k==0 or k==2:
       # cova and covc
         temp  = ( u[j]*v.Dot(v) - v[j]*u.Dot(v) )*u[i]+(u[j]*u.Dot(v)-v[j]*u.Dot(u))*v[i]
         sign = -1
         if k==2 : sign = +1
         T[i][3*k+j] = 0.5*( KD + sign*temp )/denom
        elif k==1:
       # covu
         ca= c-a
         T[i][3*k+j] = 0.5*(Va*KD + u[i]/denom**2*(denom*( ca[j]*v.Dot(v)-(v.Dot(ca)*v[j]) - \
                         (ca.Dot(u)*v.Dot(v)-ca.Dot(v)*u.Dot(v))*2*u[j]*v.Dot(v)-v[j]*u.Dot(v) ))+ \
                          v[i]/denom**2*(denom*( ca[j]*u.Dot(v)-(u.Dot(ca)*v[j]) - \
                         2*ca.Dot(v)*u[j]-(ca.Dot(u)*u.Dot(v)- ca.Dot(v)*u.Dot(u))*2*(u[j]*v.Dot(v)-v[j]*u.Dot(v)) )) )
        elif k==3:
       # covv
         ca= c-a
         T[i][3*k+j] = 0.5*(Vb*KD + u[i]/denom**2*(denom*( 2*ca.Dot(u)*v[j] - ca.Dot(v)*u[j]- \
                         ca[j]*u.Dot(v) ) - (ca.Dot(u)*v.Dot(v)-ca.Dot(v)*u.Dot(v))*2*(v[j]*u.Dot(u)-u[j]*u.Dot(v) )) + \
                          v[i]/denom**2*(denom*( ca.Dot(u)*u[j]-ca[j]*u.Dot(u) ) - \
                         (ca.Dot(u)*u.Dot(v)-ca.Dot(v)*u.Dot(u))*2*(v[j]*u.Dot(u)-u[j]*u.Dot(v)) ))   
        #print "jacob",i,3*k+j, T[i][3*k+j]
   transT = ROOT.TMatrixD(12,3)
   transT.Transpose(T)
   CovTracks = ROOT.TMatrixD(12,12)
   tlist = [t1,t2]
   for k in range(2):
     for i in range(6):
       for j in range(6): 
        xfac = 1.
        if i>2: xfac = scalFac[tlist[k]]  
        if j>2: xfac = xfac * scalFac[tlist[k]]
        CovTracks[i+k*6][j+k*6] = CovMat[tlist[k]][i][j] * xfac
        #print "cov track",i+k*6,6*k+j,  CovTracks[i+k*6][j+k*6]
   tmp   = ROOT.TMatrixD(3,12)
   tmp.Mult(T,CovTracks)
   covX  = ROOT.TMatrixD(3,3)
   covX.Mult(tmp,transT)
   return X,covX,dist
#

class ShipReco:
 " convert FairSHiP MC hits to measurements"
 def __init__(self,fout):
  self.fn = ROOT.TFile(fout,'update')
  self.sTree     = self.fn.cbmsim
  if self.sTree.GetBranch("SmearedHits"):
    print "remove RECO branches and rerun reconstruction"
    self.fn.Close()    
    # make a new file without reco branches
    f = ROOT.TFile(fout)
    sTree = f.cbmsim
    sTree.SetBranchStatus("SmearedHits",0)
    if sTree.GetBranch("FitTracks"): sTree.SetBranchStatus("FitTracks",0)
    if sTree.GetBranch("Particles"): sTree.SetBranchStatus("Particles",0)
    if sTree.GetBranch("fitTrack2MC"): sTree.SetBranchStatus("fitTrack2MC",0)
    if sTree.GetBranch("FitTracks_PR"): sTree.SetBranchStatus("FitTracks_PR",0)
    if sTree.GetBranch("Particles_PR"): sTree.SetBranchStatus("Particles_PR",0)
    if sTree.GetBranch("fitTrack2MC_PR"): sTree.SetBranchStatus("fitTrack2MC_PR",0)
    if sTree.GetBranch("EcalClusters"): sTree.SetBranchStatus("EcalClusters",0)     
    rawFile = fout.replace("_rec.root","_raw.root")
    recf = ROOT.TFile(rawFile,"recreate")
    newTree = sTree.CloneTree(0)
    for n in range(sTree.GetEntries()):
      sTree.GetEntry(n)
      rc = newTree.Fill()
    sTree.Clear()
    newTree.AutoSave()
    f.Close() 
    recf.Close() 
    os.system('cp '+rawFile +' '+fout)
    self.fn = ROOT.TFile(fout,'update')
    self.sTree     = self.fn.cbmsim     
#  check that all containers are present, otherwise create dummy version
  self.dummyContainers={}
  branch_class = {"vetoPoint":"vetoPoint","ShipRpcPoint":"ShipRpcPoint","TargetPoint":"TargetPoint",\
                  "strawtubesPoint":"strawtubesPoint","EcalPointLite":"ecalPoint","HcalPointLite":"hcalPoint"}
  for x in branch_class:
    if not self.sTree.GetBranch(x):
     self.dummyContainers[x+"_array"] = ROOT.TClonesArray(branch_class[x])
     self.dummyContainers[x] = self.sTree.Branch(x,self.dummyContainers[x+"_array"],32000,-1) 
     setattr(self.sTree,x,self.dummyContainers[x+"_array"])
     self.dummyContainers[x].Fill()
  if self.sTree.GetBranch("GeoTracks"): self.sTree.SetBranchStatus("GeoTracks",0)
  self.nEvents   = min(self.sTree.GetEntries(),nEvents)
# prepare for output
  self.fPartArray   = ROOT.TClonesArray("TParticle") 
  self.fGenFitArray = ROOT.TClonesArray("genfit::Track") 
  self.fGenFitArray.BypassStreamer(ROOT.kFALSE)
  self.fitTrack2MC  = ROOT.std.vector('int')()
  self.mcLink      = self.sTree.Branch("fitTrack2MC"+realPR,self.fitTrack2MC,32000,-1)
  self.fitTracks   = self.sTree.Branch("FitTracks"+realPR,  self.fGenFitArray,32000,-1)
  self.Particles   = self.sTree.Branch("Particles"+realPR,  self.fPartArray,32000,-1)
#
  self.SmearedHits     = ROOT.TClonesArray("TVectorD") 
  self.SHbranch       = self.sTree.Branch("SmearedHits",self.SmearedHits,32000,-1)
#
  self.LV={1:ROOT.TLorentzVector(),2:ROOT.TLorentzVector()}
  self.reps,self.states,self.newPosDir = {},{},{}
#
  self.random = ROOT.TRandom()
  ROOT.gRandom.SetSeed(13)

 def hit2wire(self,ahit,no_amb=None):
     detID = ahit.GetDetectorID()
     top = ROOT.TVector3()
     bot = ROOT.TVector3()
     modules["Strawtubes"].StrawEndPoints(detID,bot,top)
     ex = ahit.GetX()
     ey = ahit.GetY()
     ez = ahit.GetZ()
   #distance to wire, and smear it.
     dw  = ahit.dist2Wire()
     smear = dw
     if not no_amb: smear = ROOT.fabs(self.random.Gaus(dw,ShipGeo.straw.resol))
     smearedHit = {'mcHit':ahit,'xtop':top.x(),'ytop':top.y(),'z':top.z(),'xbot':bot.x(),'ybot':bot.y(),'z':bot.z(),'dist':smear}
     # print 'smeared hit:',top.x(),top.y(),top.z(),bot.x(),bot.y(),bot.z(),"dist",smear,ex,ey,ez,ox,oy,oz
     if abs(top.y())==abs(bot.y()): h['disty'].Fill(dw)
     if abs(top.y())>abs(bot.y()): h['distu'].Fill(dw)
     if abs(top.y())<abs(bot.y()): h['distv'].Fill(dw)
     return smearedHit
  
 def execute(self,n):
  if n > self.nEvents-1: return None 
  rc    = self.sTree.GetEvent(n) 
  if n%1000==0: print "==> event ",n
  nShits = self.sTree.strawtubesPoint.GetEntriesFast() 
  hitPosLists    = {}
  stationCrossed = {}
  fittedtrackids=[]
  self.SmearedHits.Delete()
  self.fPartArray.Delete()
  self.fGenFitArray.Delete()
  self.fitTrack2MC.clear()
#   
  for i in range(nShits):
    ahit = self.sTree.strawtubesPoint.At(i)
    sm   = self.hit2wire(ahit,withNoStrawSmearing)
    m = array('d',[i,sm['xtop'],sm['ytop'],sm['z'],sm['xbot'],sm['ybot'],sm['z'],sm['dist'],ahit.GetDetectorID()])
    measurement = ROOT.TVectorD(9,m)
# copy to branch
    nHits = self.SmearedHits.GetEntries()
    if self.SmearedHits.GetSize() == nHits: self.SmearedHits.Expand(nHits+1000)
    self.SmearedHits[nHits] = measurement
    station = int(ahit.GetDetectorID()/10000000)
    if station > 4 : continue
    # do not use hits in Veto station for track reco   
    trID = ahit.GetTrackID()
    if not hitPosLists.has_key(trID):   
      hitPosLists[trID]     = ROOT.std.vector('TVectorD')()
      stationCrossed[trID]  = {}
    m = array('d',[sm['xtop'],sm['ytop'],sm['z'],sm['xbot'],sm['ybot'],sm['z'],sm['dist']])
    hitPosLists[trID].push_back(ROOT.TVectorD(7,m))
    if not stationCrossed[trID].has_key(station): stationCrossed[trID][station]=0
    stationCrossed[trID][station]+=1   
  nTrack = -1
  if realPR:
     fittedtrackids=shipPatRec.execute(n,self.SmearedHits,self.sTree,shipPatRec.ReconstructibleMCTracks)
     if fittedtrackids:
       tracknbr=0
       for ids in fittedtrackids:
	 nTrack   = SHiP.fGenFitArray.GetEntries()
         theTrack = shipPatRec.theTracks[tracknbr]
         if not debug: theTrack.prune("CFL")  #  http://sourceforge.net/p/genfit/code/HEAD/tree/trunk/core/include/Track.h#l280 
         self.fGenFitArray[nTrack] = theTrack
         self.fitTrack2MC.push_back(ids) 
	 tracknbr+=1
  else: # do fake pattern reco	 
   for atrack in hitPosLists:
    if atrack < 0: continue # these are hits not assigned to MC track because low E cut
    pdg    = self.sTree.MCTrack[atrack].GetPdgCode()
    if not PDG.GetParticle(pdg): continue # unknown particle
    meas = hitPosLists[atrack]
    nM = meas.size()
    if nM < 25 : continue                          # not enough hits to make a good trackfit 
    if len(stationCrossed[atrack]) < 3 : continue  # not enough stations crossed to make a good trackfit 
    if debug: 
       mctrack = self.sTree.MCTrack[atrack]
    charge = PDG.GetParticle(pdg).Charge()/(3.)
    posM = ROOT.TVector3(0, 0, 0)
    momM = ROOT.TVector3(0,0,3.*u.GeV)
# approximate covariance
    covM = ROOT.TMatrixDSym(6)
    resolution = ShipGeo.straw.resol
    for  i in range(3):   covM[i][i] = resolution*resolution
    covM[0][0]=resolution*resolution*100.
    for  i in range(3,6): covM[i][i] = ROOT.TMath.pow(resolution / nM / ROOT.TMath.sqrt(3), 2)
# trackrep
    rep = ROOT.genfit.RKTrackRep(pdg)
# smeared start state
    stateSmeared = ROOT.genfit.MeasuredStateOnPlane(rep)
    rep.setPosMomCov(stateSmeared, posM, momM, covM)
# create track
    seedState = ROOT.TVectorD(6)
    seedCov   = ROOT.TMatrixDSym(6)
    rep.get6DStateCov(stateSmeared, seedState, seedCov)
    theTrack = ROOT.genfit.Track(rep, seedState, seedCov)
    hitCov = ROOT.TMatrixDSym(7)
    hitCov[6][6] = resolution*resolution
    for m in meas:
      tp = ROOT.genfit.TrackPoint(theTrack) # note how the point is told which track it belongs to 
      measurement = ROOT.genfit.WireMeasurement(m,hitCov,1,6,tp) # the measurement is told which trackpoint it belongs to
      # print measurement.getMaxDistance()
      measurement.setMaxDistance(0.5*u.cm)
      # measurement.setLeftRightResolution(-1)
      tp.addRawMeasurement(measurement) # package measurement in the TrackPoint                                          
      theTrack.insertPoint(tp)  # add point to Track
   # print "debug meas",atrack,nM,stationCrossed[atrack],self.sTree.MCTrack[atrack],pdg
#check
    if not theTrack.checkConsistency():
     print 'Problem with track before fit, not consistent',atrack,theTrack
     continue
# do the fit
    try:  fitter.processTrack(theTrack) # processTrackWithRep(theTrack,rep,True)
    except: 
       print "genfit failed to fit track"
       continue
#check
    if not theTrack.checkConsistency():
     print 'Problem with track after fit, not consistent',atrack,theTrack
     continue
    fitStatus   = theTrack.getFitStatus()
    nmeas = fitStatus.getNdf()   
    chi2        = fitStatus.getChi2()/nmeas   
    h['chi2'].Fill(chi2)
# make track persistent
    nTrack   = SHiP.fGenFitArray.GetEntries()
    if not debug: theTrack.prune("CFL")  #  http://sourceforge.net/p/genfit/code/HEAD/tree/trunk/core/include/Track.h#l280 
    self.fGenFitArray[nTrack] = theTrack
    self.fitTrack2MC.push_back(atrack)
    if debug: 
     print 'save track',theTrack,chi2,nM,fitStatus.isFitConverged()
  return nTrack+1
#
 def find2TrackVertex(self):
  fittedTracks = self.fGenFitArray
  particles    = self.fPartArray
  PosDirCharge,CovMat,scalFac = {},{},{}
  for tr in range(fittedTracks.GetEntries()):
   fitStatus = fittedTracks[tr].getFitStatus()
   if not fitStatus.isFitConverged(): continue
   nmeas = fitStatus.getNdf()
   chi2  = fitStatus.getChi2()/nmeas
   if chi2<50 and not chi2<0: 
      xx  = fittedTracks[tr].getFittedState()
      pid   = xx.getPDG()
      if not pidProton and abs(pid) == 2212:
        pid = ROOT.TMath.Sign(211,pid)
      rep   = ROOT.genfit.RKTrackRep(xx.getPDG())  
      state = ROOT.genfit.StateOnPlane(rep)
      rep.setPosMom(state,xx.getPos(),xx.getMom())
      PosDirCharge[tr] = {'position':xx.getPos(),'direction':xx.getDir(),\
                          'momentum':xx.getMom(),'charge':xx.getCharge(),'pdgCode':pid,'state':xx,'rep':rep,'newstate':state}
      CovMat[tr] = xx.get6DCov() 
#
  if len(PosDirCharge) < 2: return
  if len(PosDirCharge) > 4: return # abort too busy events
  for t1 in PosDirCharge:
   c1  = PosDirCharge[t1]['charge'] 
   for t2 in PosDirCharge:
     if not t2>t1: continue
     # ignore this for background studies 
     if PosDirCharge[t2]['charge'] == c1 : continue
     newPos,doca    = myVertexError(t1,t2,PosDirCharge)
# as we have learned, need iterative procedure
     dz = 99999.
     rc = True 
     step = 0
     while dz > 0.01:
      zBefore = newPos[2]
     # make a new rep for track 1,2
      for tr in [t1,t2]:     
       try:
        PosDirCharge[tr]['rep'].extrapolateToPoint(PosDirCharge[tr]['newstate'], newPos, False)
       except:
        print 'SHiPReco: extrapolation did not worked'
        rc = False  
        break
       self.newPosDir[tr] = {'position':PosDirCharge[tr]['rep'].getPos(PosDirCharge[tr]['newstate']),\
                             'direction':PosDirCharge[tr]['rep'].getDir(PosDirCharge[tr]['newstate']),\
                             'momentum':PosDirCharge[tr]['rep'].getMom(PosDirCharge[tr]['newstate'])}
      if not rc: break
      newPos,doca = myVertexError(t1,t2,self.newPosDir)
      dz = abs(zBefore-newPos[2])
      step+=1
      if step > 10:  
         print 'abort iteration, too many steps, pos=',newPos[0],newPos[1],newPos[2],' doca=',doca,'z before and dz',zBefore,dz
         rc = False
         break 
#       
     if not rc: continue # extrapolation failed, makes no sense to continue
# now go for the last step and vertex error
     scalFac[t1] = (PosDirCharge[t1]['position'][2]-newPos[2])/PosDirCharge[t1]['direction'][2]/PosDirCharge[t1]['momentum'].Mag()
     scalFac[t2] = (PosDirCharge[t2]['position'][2]-newPos[2])/PosDirCharge[t2]['direction'][2]/PosDirCharge[t2]['momentum'].Mag()
     HNLPos,covX,dist = myVertexError(t1,t2,self.newPosDir,CovMat,scalFac)
# monitor Vx resolution and pulls
     #print "DEBUG",HNLPos[0],HNLPos[1],HNLPos[2],dist,covX[0][0],covX[1][1],covX[2][2]
     #print "     ",mctrack.GetStartX(),mctrack.GetStartY(),mctrack.GetStartZ()
#   HNL true
     mctrack = self.sTree.MCTrack[self.sTree.fitTrack2MC[t1]]
     h['Vzpull'].Fill( (mctrack.GetStartZ()-HNLPos[2])/ROOT.TMath.Sqrt(covX[2][2]) )
     h['Vxpull'].Fill( (mctrack.GetStartX()-HNLPos[0])/ROOT.TMath.Sqrt(covX[0][0]) )
     h['Vypull'].Fill( (mctrack.GetStartY()-HNLPos[1])/ROOT.TMath.Sqrt(covX[1][1]) )
#
     pid = PosDirCharge[t1]['pdgCode']
     mass = PDG.GetParticle(pid).Mass()
     mom  = self.newPosDir[t1]['momentum']
     E = ROOT.TMath.Sqrt( mass*mass + mom.Mag2() )
     self.LV[1].SetPxPyPzE(mom.x(),mom.y(),mom.z(),E)
     pid = PosDirCharge[t2]['pdgCode']
     mass = PDG.GetParticle(pid).Mass()
     mom  = self.newPosDir[t2]['momentum']
     E = ROOT.TMath.Sqrt( mass*mass + mom.Mag2() )
     self.LV[2].SetPxPyPzE(mom.x(),mom.y(),mom.z(),E)
     HNL = self.LV[1]+self.LV[2]
# try to make it persistent
     vx = ROOT.TLorentzVector(HNLPos,doca)  # misuse time as DOCA  
     particle = ROOT.TParticle(9900015,0,-1,-1,t1,t2,HNL,vx)
     particle.SetMother(1,99) # as marker to remember doca is set
     nParts   = particles.GetEntries()
     particles[nParts] = particle

# -----Calorimeter part --------------------------------------------
# Creates. exports and fills calorimeter structure
dflag = 0
if debug: dflag = 10

# access ShipTree
SHiP = ShipReco(outFile)
SHiP.sTree.GetEvent(0)

caloTasks = []  
if SHiP.sTree.GetBranch("EcalPoint"):
 ecalGeo = ecalGeoFile+'z'+str(ShipGeo.ecal.z)+".geo"
 ecalFiller=ROOT.ecalStructureFiller("ecalFiller", dflag,ecalGeo)
 ecalFiller.SetUseMCPoints(ROOT.kTRUE)
 ecalFiller.StoreTrackInformation()
 caloTasks.append(ecalFiller)
 #GeV -> ADC conversion
 ecalDigi=ROOT.ecalDigi("ecalDigi",0)
 caloTasks.append(ecalDigi)
 #ADC -> GeV conversion
 ecalPrepare=ROOT.ecalPrepare("ecalPrepare",0)
 caloTasks.append(ecalPrepare)
 # Maximums locator
 ecalMaximumFind=ROOT.ecalMaximumLocator("maximumFinder",dflag)
 caloTasks.append(ecalMaximumFind)
 # Cluster calibration
 ecalClusterCalib=ROOT.ecalClusterCalibration("ecalClusterCalibration", 0)
 #4x4 cm cells
 ecalCl3PhS=ROOT.TFormula("ecalCl3PhS", "[0]+x*([1]+x*([2]+x*[3]))")
 ecalCl3PhS.SetParameters(6.77797e-04, 5.75385e+00, 3.42690e-03, -1.16383e-04)
 ecalClusterCalib.SetStraightCalibration(3, ecalCl3PhS)
 ecalCl3Ph=ROOT.TFormula("ecalCl3Ph", "[0]+x*([1]+x*([2]+x*[3]))+[4]*x*y+[5]*x*y*y")
 ecalCl3Ph.SetParameters(0.000750975, 5.7552, 0.00282783, -8.0025e-05, -0.000823651, 0.000111561)
 ecalClusterCalib.SetCalibration(3, ecalCl3Ph)
 #6x6 cm cells
 ecalCl2PhS=ROOT.TFormula("ecalCl2PhS", "[0]+x*([1]+x*([2]+x*[3]))")
 ecalCl2PhS.SetParameters(8.14724e-04, 5.67428e+00, 3.39030e-03, -1.28388e-04)
 ecalClusterCalib.SetStraightCalibration(2, ecalCl2PhS)
 ecalCl2Ph=ROOT.TFormula("ecalCl2Ph", "[0]+x*([1]+x*([2]+x*[3]))+[4]*x*y+[5]*x*y*y")
 ecalCl2Ph.SetParameters(0.000948095, 5.67471, 0.00339177, -0.000122629, -0.000169109, 8.33448e-06)
 ecalClusterCalib.SetCalibration(2, ecalCl2Ph)
 caloTasks.append(ecalClusterCalib)
 # Cluster finder
 ecalClusterFind=ROOT.ecalClusterFinder("clusterFinder",dflag)
 caloTasks.append(ecalClusterFind)#
 if EcalDebugDraw:
  # ecal drawer: Draws calorimeter structure, incoming particles, clusters, maximums
  ecalDrawer=ROOT.ecalDrawer("clusterFinder",10)
  caloTasks.append(ecalDrawer)
 ecalStructure=ecalFiller.InitPython(SHiP.sTree.EcalPointLite)
 ecalDigi.InitPython(ecalStructure)
 ecalPrepare.InitPython(ecalStructure)
 ecalMaximums=ecalMaximumFind.InitPython(ecalStructure)
 ecalCalib=ecalClusterCalib.InitPython()
 ecalClusters=ecalClusterFind.InitPython(ecalStructure, ecalMaximums, ecalCalib)
 SHiP.EcalClusters = SHiP.sTree.Branch("EcalClusters",ecalClusters,32000,-1)
 if EcalDebugDraw: ecalDrawer.InitPython(SHiP.sTree.MCTrack, SHiP.sTree.EcalPoint, ecalStructure, ecalClusters)
else:
 ecalClusters = ROOT.TClonesArray("ecalCluster") 
SHiP.EcalClusters = SHiP.sTree.Branch("EcalClusters",ecalClusters,32000,-1)

geoMat =  ROOT.genfit.TGeoMaterialInterface()
PDG = ROOT.TDatabasePDG.Instance()
# init geometry and mag. field
gMan  = ROOT.gGeoManager
#
bfield = ROOT.genfit.BellField(ShipGeo.Bfield.max ,ShipGeo.Bfield.z,2, ShipGeo.Yheight/2.*u.m)
fM = ROOT.genfit.FieldManager.getInstance()
fM.init(bfield)
 
geoMat =  ROOT.genfit.TGeoMaterialInterface()
ROOT.genfit.MaterialEffects.getInstance().init(geoMat)

if debug: fitter.setDebugLvl(1) # produces lot of printout
WireMeasurement = ROOT.genfit.WireMeasurement

# for 'real' PatRec
shipPatRec.initialize(fgeo)

# main loop
for iEvent in range(firstEvent, SHiP.nEvents):
 if debug: print 'event ',iEvent
 ntracks = SHiP.execute(iEvent)
 if vertexing:
# now go for 2-track combinations
   if ntracks > 1: SHiP.find2TrackVertex()
# make tracks and particles persistent
 SHiP.Particles.Fill()
 SHiP.fitTracks.Fill()
 SHiP.mcLink.Fill()
 SHiP.SHbranch.Fill()
 for x in caloTasks: x.Exec('start')
 SHiP.EcalClusters.Fill()

 if debug: print 'end of event after Fill'
 
# end loop over events

print 'finished writing tree'
SHiP.sTree.Write()

ut.writeHists(h,"recohists.root")
if realPR: ut.writeHists(shipPatRec.h,"recohists_patrec.root")

