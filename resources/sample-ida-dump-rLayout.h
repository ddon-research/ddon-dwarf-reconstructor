struct rLayout::SetInfo;

rLayout::MyDTI stru_25942D0; // idb
rLayout::SetInfo::MyDTI stru_2594308; // idb
MtObject *__fastcall rLayout::MyDTI::newInstance(const rLayout::MyDTI *this);
void __fastcall rLayout::_rLayout(rLayout *this);
void __fastcall rLayout::destruct(rLayout *this);
void __fastcall rLayout::_rLayout_0(rLayout *this);
bool __fastcall rLayout::load(rLayout *this, MtStream *in);
void __fastcall rLayout::filePath2LayoutID(rLayout::TYPE *lotType, nLayout::stLayoutID *layoutID, MT_CTSTR filePath);
void __fastcall rLayout::filePath2SplitID(nLayout::stSplitID *splitID, MT_CTSTR filePath);
void __fastcall rLayout::clear(rLayout *this);
MtObject *__fastcall rLayout::SetInfo::MyDTI::newInstance(const rLayout::SetInfo::MyDTI *this);
void __fastcall rLayout::SetInfo::_SetInfo(rLayout::SetInfo *this);
void __fastcall rLayout::SetInfo::_SetInfo_0(rLayout::SetInfo *this);
void __fastcall rLayout::SetInfo::createProperty(rLayout::SetInfo *this, MtPropertyList *s);
s32 __fastcall rLayout::SetInfo::getID(const rLayout::SetInfo *this);
void __fastcall rLayout::SetInfo::setID(rLayout::SetInfo *this, s32 val);
MT_CTSTR __fastcall rLayout::SetInfo::getName(rLayout::SetInfo *this);
bool __fastcall rLayout::SetInfo::load(rLayout::SetInfo *this, MtDataReader *r, rLayout::SetInfoBuffer *buffer);
__int64 __fastcall rLayout::SetInfo::getSetPos(__int64 a1, const rLayout::SetInfo *this);
u32 __fastcall rLayout::SetInfo::getArea(const rLayout::SetInfo *this);
void __fastcall rLayout::SetInfo::setArea(rLayout::SetInfo *this, u32 area);
u32 __fastcall rLayout::SetInfo::getGroup(const rLayout::SetInfo *this);
void __fastcall rLayout::SetInfo::setGroup(rLayout::SetInfo *this, u32 group);
s32 __fastcall rLayout::SetInfo::getSplitX(const rLayout::SetInfo *this);
void __fastcall rLayout::SetInfo::setSplitX(rLayout::SetInfo *this, u32 x);
s32 __fastcall rLayout::SetInfo::getSplitZ(const rLayout::SetInfo *this);
void __fastcall rLayout::SetInfo::setSplitZ(rLayout::SetInfo *this, u32 z);
void __fastcall rLayout::SetInfo::setDummy(rLayout::SetInfo *this, const MtString *);
const MtDTI *__fastcall rLayout::getDTI(const rLayout *this);
MT_CTSTR __fastcall rLayout::getExt(const rLayout *this);
rLayout::SetInfo *__fastcall rLayout::getSetInfo(const rLayout *this, u32 index);
u32 __fastcall rLayout::getSetInfoNum(const rLayout *this);
s32 __fastcall rLayout::getID(const rLayout *this, u32 no);
const MtDTI *__fastcall rLayout::SetInfo::getDTI(const rLayout::SetInfo *this);

enum rLayout::TYPE : __int32
{
  rLayout::TYPE::TYPE_SCR = 0x0,
  rLayout::TYPE::TYPE_PLAN = 0x1,
  rLayout::TYPE::TYPE_ENEMY = 0x2,
  rLayout::TYPE::TYPE_NPC = 0x3,
  rLayout::TYPE::TYPE_TARGET = 0x4,
  rLayout::TYPE::TYPE_NUM = 0x5,
};

struct __cppobj rLayout::SetInfo : MtObject
{
  s32 mID;
  cSetInfo *mpInfo;
  nLayout::stLayoutID mLayoutID;
  nLayout::stSplitID mSplitID;
};

struct __cppobj rLayout::SetInfo::MyDTI : MtDTI
{
};

struct __cppobj rLayout::MyDTI : MtDTI
{
};

struct rLayout::SetInfoBuffer
{
  cSetInfoEnemy *pSetInfoEnemy;
  cSetInfoNpc *pSetInfoNpc;
  cSetInfoGeneralPoint *pSetInfoGeneralPoint;
  cSetInfoOm *pSetInfoOm;
  cSetInfoOmBoard *pSetInfoOmBoard;
  cSetInfoOmBowlOfLife *pSetInfoOmBowlOfLife;
  cSetInfoOmCtrl *pSetInfoOmCtrl;
  cSetInfoOmDoor *pSetInfoOmDoor;
  cSetInfoOmElfSW *pSetInfoOmElfSW;
  cSetInfoOmFall *pSetInfoOmFall;
  cSetInfoOmGather *pSetInfoOmGather;
  cSetInfoOmTreasureBox *pSetInfoOmTreasureBox;
  cSetInfoOmHakuryuu *pSetInfoOmHakuryuu;
  cSetInfoOmHeal *pSetInfoOmHeal;
  cSetInfoOmLadder *pSetInfoOmLadder;
  cSetInfoOmLever *pSetInfoOmLever;
  cSetInfoOmNav *pSetInfoOmNav;
  cSetInfoOmRange *pSetInfoOmRange;
  cSetInfoOmText *pSetInfoOmText;
  cSetInfoOmWall *pSetInfoOmWall;
  cSetInfoOmWarp *pSetInfoOmWarp;
  cSetInfoOmBadStatus *pSetInfoOmBadStatus;
  MtArray *pSetInfoSingleNewArray;
  u32 AvailNums[22];
};

enum rLayout::SET_INFO_ALLOC : __int32
{
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_ENEMY = 0x0,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_NPC = 0x1,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_GENERALPOINT = 0x2,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM = 0x3,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_BOARD = 0x4,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_BOWLOFLIFE = 0x5,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_CTRL = 0x6,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_DOOR = 0x7,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_ELFSW = 0x8,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_FALL = 0x9,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_GATHER = 0xA,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_TREASUREBOX = 0xB,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_HAKURYUU = 0xC,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_HEAL = 0xD,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_LADDER = 0xE,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_LEVER = 0xF,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_NAV = 0x10,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_RANGE = 0x11,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_TEXT = 0x12,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_WALL = 0x13,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_WARP = 0x14,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_OM_BADSTATUS = 0x15,
  rLayout::SET_INFO_ALLOC::SET_INFO_ALLOC_NUM = 0x16,
};
