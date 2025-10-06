struct __cppobj MtObject
{
  int (**_vptr$MtObject)(void);
};

struct __cppobj cSetInfo : MtObject
{
};

struct __cppobj cSetInfo::MyDTI : MtDTI
{
};

struct __cppobj __attribute__((aligned(8))) cSetInfoCoord : cSetInfo
{
  MtString mName;
  MtFloat3 mPosition;
  MtFloat3 mAngle;
  MtFloat3 mScale;
  s32 mUnitID;
  s32 mAreaHitNo;
  u32 mVersion;
  s32 mTblIndex;
};

struct __cppobj cSetInfoOm : cSetInfoCoord
{
  bool mDisableEffect;
  bool mDisableOnlyEffect;
  bool mOpenFlag;
  bool mEnableSyncLight;
  bool mEnableZone;
  u32 mInitMtnNo;
  u32 mAreaMasterNo;
  u16 mAreaReleaseNo;
  bool mAreaReleaseON;
  bool mAreaReleaseOFF;
  u32 mWarpPointId;
  u32 mKeyNo;
  bool mIsBreakLink;
  bool mIsBreakQuest;
  u16 mBreakKind;
  u16 mBreakGroup;
  u16 mBreakID;
  u32 mQuestFlag;
  bool mIsNoSbc;
  bool mIsMyQuest;
};

struct __cppobj __attribute__((aligned(8))) cSetInfoOmBreakTarget : cSetInfoOm
{
  u32 mBreakHitNum;
};

struct __cppobj cSetInfoOmBreakTarget::MyDTI : MtDTI
{
};
