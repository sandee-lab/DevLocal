# 번역 모델 비교 검수표 — 영문(EN)

- 작성일: 2026-09-02
- 비교 모델: **grok-4.3** (현행) vs **grok-4.6@low** (검토 대상)
- 대상 시트: Dialogue, Mail, Unit
- 원문·번역은 실제 시트 데이터이며, 동일 프롬프트·동일 조건에서 각 모델이 생성한 결과입니다.

## 검수 방법

1. 두 모델의 번역이 **다른 항목만** 아래에 실었습니다 (동일한 항목은 판단이 필요 없으므로 제외).
2. 각 항목의 `선택` 칸에 더 나은 쪽을 표기해 주세요 — `A`(현행) / `B`(검토 대상) / `둘다OK` / `둘다NG`.
3. `자동검증` 칸은 툴이 정규식으로 잡아낸 결함입니다. 태그(`{변수}`, `\n`, `<color>` 등) 누락과 한국어 잔존만 기계적으로 검사한 것이라, **문체·의미의 적절성은 사람 판단이 필요합니다**.

## 요약

| 항목 | 값 |
|---|---|
| 비교 대상 행 | 150행 |
| 두 모델 번역 동일 | 48행 (32%) |
| **번역 상이 (검수 대상)** | **102행 (68%)** |
| 자동검증 결함 — grok-4.3 | 4행 |
| 자동검증 결함 — grok-4.6@low | 0행 |

## Dialogue 시트 — 상이 41건

### 단문 (30건)

| Key | 원문(KO) | A. grok-4.3 | B. grok-4.6@low | 자동검증 | 선택 |
|---|---|---|---|---|---|
| `local_dialogue_1011` | [위치 상태 : 콰챠 갤럭시]\n좌표는 '안전 및 규정 준수' 구역을 한참 벗어남. | [Location Status: Quacha Galaxy]\nCoordinates are way outside the 'Safety and Compliance' zone. | [Location status: Kwacha Galaxy]\nCoordinates are way outside the 'Safety & Compliance' zone. | OK | |
| `local_dialogue_1012` | 대체 무슨 상황인거죠?\n모든 시스템이 경고를 띄우고 있어요. | What the heck is going on?\nAll systems are flashing warnings. | What on earth is going on?\nEvery system is screaming warnings. | OK | |
| `local_dialogue_2011` | 당신. 당신이 워프 중 메인 케이블을 씹었죠.\n내 배송 일정을 망친 주범이군요. | You. You're the one who chewed through the main cable during warp.\nThe culprit who wrecked my delivery schedule. | You. You chewed the main cable mid-warp.\nYou're the one who wrecked my delivery schedule. | OK | |
| `local_dialogue_2012` | 당장 상자에 다시 들어가세요.\n'운송 중 위험 요소'를 내 전투 파트너로 둘 생각은 없습니다. | Get back in the box right now.\nI have zero intention of making a 'transport hazard' my combat partner. | Get back in the box, now.\nI'm not making a 'in-transit hazard' my combat partner. | OK | |
| `local_dialogue_2021` | 야옹!\n(해석: 와, 공기 좋다! 이제 뭐 좀 썰어 볼까?) | Meow!\n(Translation: Whoa, fresh air! Time to slice some stuff!) | Meow!\n(Translation: Whoa, nice air! Time to slice something up?) | OK | |
| `local_dialogue_2031` | (한숨) 아무래도 불량 유닛으로 보입니다.\n이게 바로 슈뢰딩거 시스템인가요? | (Sigh) Looks like a defective unit.\nSo this is the Schrödinger System, huh? | (Sigh) Looks like a defective unit.\nSo this is the Schrödinger System? | OK | |
| `local_dialogue_3021` | (한숨) 무료 지원은 안 돼요. 내 권한 밖입니다.\n가능한 옵션은 하나 있네요. | (Sigh) Free support isn't happening. It's outside my authority.\nBut there is one option available. | (Sigh) Free support? Nope. Above my pay grade.\nThere is one option, though. | OK | |
| `local_dialogue_3022` | 긴급 유닛 투하를 승인할게요.\n활성화 수수료 150만 미네랄은 다음 급여에서 차감합니다. | I'll authorize an emergency unit drop.\nThe 1.5 million mineral activation fee will be deducted from your next paycheck. | I'll authorize an emergency unit drop.\nThe 1.5 million mineral activation fee comes out of your next paycheck. | OK | |
| `local_dialogue_3031` | 150만 미네랄요?\n제 급여로는 감당이 안 됩니다! | 1.5 million minerals?\nMy salary can't handle that! | 1.5 million minerals?\nMy salary can't cover that! | OK | |
| `local_speech_bubble_intro_02` | 현재 위치는... | Current location... | Current location is... | OK | |
| `local_speech_bubble_intro_03` | '회사가 책임지지 않는 구역' | 'Company Non-Liability Zone' | 'A zone the company won't take responsibility for' | OK | |
| `local_speech_bubble_intro_04` | 다른 건 몰라도... | One thing's for sure... | Whatever else happens... | OK | |
| `local_speech_bubble_intro_05` | 빅 보스의 상자는 꼭 찾아야 해...! | Gotta find the Big Boss's box no matter what...! | I have to find the Big Boss's box...! | OK | |
| `local_speech_bubble_intro_07` | 외계인이 사방에서 몰려오네! | Aliens are swarming from everywhere! | Aliens are pouring in from everywhere! | OK | |
| `local_speech_bubble_intro_09` | 저거 츄르 상자인가? 무조건 잡아! | Is that the Churu box? Gotta grab it no matter what! | Is that a Churu box? Grab it no matter what! | OK | |
| `local_speech_bubble_intro_11` | 못 찾으면 '통조림 따개'로 강등이야! | If we don't find it, we're getting demoted to 'can openers'! | If I don't find it, I'm getting demoted to 'can opener'! | OK | |
| `local_speech_bubble_intro_12` | 이번 상자는 무조건 '전설'이야! | This box is definitely a 'Legend'! | This box is definitely 'Legendary'! | OK | |
| `local_speech_bubble_intro_13` | 보충 유닛 도착! | Backup units have arrived! | Reinforcement units have arrived! | OK | |
| `local_speech_bubble_intro_14` | 겨우 이것들 때문에\n호출한 건가? | You called us for just these guys? | You called me\nfor these? | A:⚠️ 태그 / B:OK | |
| `local_speech_bubble_intro_15` | 목표 발견, 목표 발견. | Target acquired, target acquired. | Target spotted, target spotted. | OK | |
| `local_tutorial_2_01` | 새로운 행성 좌표를 스캔합니다. | Scanning for new planetary coordinates. | Scanning coordinates for a new planet. | OK | |
| `local_tutorial_2_03` | 404, 이곳은 카마존 비행선입니다.\n부대를 관리하세요. 효율적인 관리가 곧 생존입니다. | 404, this is the Kamazon spaceship.\nManage your squad. Efficient management is survival. | 404, this is a Kamazon starship.\nManage your squad. Efficient management is survival. | OK | |
| `local_tutorial_2_04` | 전투 유닛을 <color=#0674AC>3회 소환</color>하세요.\n비용은 본인 부담입니다. | Summon <color=#0674AC>combat units 3 times</color>.\nAll costs are on you. | <color=#0674AC>Summon combat units 3 times</color>.\nYou pay the bill. | OK | |
| `local_tutorial_5_01` | 이런, <color=#0674AC>보스 조우 확률 100%</color>입니다.\n부디 제대로 준비하세요. | Uh-oh, <color=#0674AC>boss encounter chance is 100%</color>.\nHope you're properly prepared. | Uh-oh, <color=#0674AC>boss encounter chance: 100%</color>.\nPlease actually be ready. | OK | |
| `local_tutorial_intro_00` | 콰챠 갤럭시의\n이름 모를 불모지... | The nameless wasteland of Quacha Galaxy...\n | Some nameless wasteland\nin the Kwacha Galaxy... | A:⚠️ 태그 / B:OK | |
| `local_tutorial_intro_02` | 확인. 상자 확보.\n특이 사항은 없음...? | Confirmed. Box secured.\nNothing unusual...? | Confirmed. Box secured.\nNo anomalies...?  | OK | |
| `local_tutorial_intro_03` | 이동하며 적들을 피하십시오.\n적과 가까워지면 <color=#0674AC>자동 공격</color>합니다. | Dodge enemies while moving.\nYou'll <color=#0674AC>auto-attack</color> when you get close. | Keep moving and dodge enemies.\nGet close and you'll <color=#0674AC>auto-attack</color>. | OK | |
| `local_tutorial_intro_04` | 404, 긴급 유닛 투하 준비됐습니다.\n호출하세요. 취소해도 비용은 청구됩니다. | 404, emergency unit drop is ready.\nCall it in. You'll still get billed even if you cancel. | 404, emergency unit drop is ready.\nCall it in. Canceling still gets billed. | OK | |
| `local_tutorial_summary_unit_reroll_01` | 유닛 리롤 및 폐기 | Unit Reroll & Discard | Unit Reroll & Scrap | OK | |
| `local_tutorial_summary_unit_reroll_02` | <color=#F3B33E>불필요한 유닛</color>을 아래로 드래그해보세요. | Try dragging <color=#F3B33E>unnecessary units</color> downward. | Try dragging an <color=#F3B33E>unwanted unit</color> downward. | OK | |

### 장문 (11건)

#### `local_dialogue_1021`

**원문(KO)**

```
당신의 용납할 수 없는 '프로토콜 7-베타 준수 실패' 때문에, 이 구역 전체가 '적대적 회수 구역'으로 간주됩니다.
```

**A. grok-4.3** — 자동검증: OK

```
Thanks to your unforgivable 'Protocol 7-Beta Compliance Failure', this entire zone is now labeled 'Hostile Recovery Zone'.
```

**B. grok-4.6@low** — 자동검증: OK

```
Because of your unforgivable 'Protocol 7-Beta compliance failure,' this entire sector is now classified as a 'Hostile Recovery Zone.'
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_2_02`

**원문(KO)**

```
<color=#0674AC>미네랄</color>을 채집해 부대를 강화하세요.\n당신도 강해지고, 회사 매출도 오르고. 일석이조죠!
```

**A. grok-4.3** — 자동검증: OK

```
Collect <color=#0674AC>minerals</color> to strengthen your squad.\nYou get stronger, company revenue goes up. Win-win!
```

**B. grok-4.6@low** — 자동검증: OK

```
Gather <color=#0674AC>Minerals</color> to power up your squad.\nYou get stronger, company revenue goes up. Two birds, one stone!
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_2_05`

**원문(KO)**

```
동일한 유닛을 <color=#0674AC>합성</color>해 등급을 높이세요.\n두 명의 인건비로 한 명만 굴릴 수 있는 혁신적인 방법이죠.
```

**A. grok-4.3** — 자동검증: OK

```
<color=#0674AC>Merge</color> identical units to raise their rank.\nA revolutionary way to pay one salary instead of two.
```

**B. grok-4.6@low** — 자동검증: OK

```
<color=#0674AC>Merge</color> identical units to raise their rank.\nPay two salaries, run one unit. Revolutionary, right?
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_2_06`

**원문(KO)**

```
<color=#0674AC>경험치</color>를 모아 카드를 획득하세요.\n카드가 많을수록 당신의 생존율이 오릅니다.
```

**A. grok-4.3** — 자동검증: OK

```
Gather <color=#0674AC>EXP</color> to obtain cards.\nMore cards means higher survival odds.
```

**B. grok-4.6@low** — 자동검증: OK

```
Collect <color=#0674AC>EXP</color> to get cards.\nMore cards, better odds you don't get scrapped.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_2_07`

**원문(KO)**

```
<color=#0674AC>강력 자석</color>으로 경험치를 당기세요.\n노동력을 아끼는 좋은 방법입니다.
```

**A. grok-4.3** — 자동검증: OK

```
Pull in EXP with the <color=#0674AC>Power Magnet</color>.\nA great way to save on labor.
```

**B. grok-4.6@low** — 자동검증: OK

```
Pull in EXP with a <color=#0674AC>Power Magnet</color>.\nA great way to save on labor.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_7_01`

**원문(KO)**

```
성공적인 행성 소거를 축하합니다!\n당신의 노고는 <color=#0674AC>소정의 위험수당</color>으로 대체되었습니다.
```

**A. grok-4.3** — 자동검증: OK

```
Congratulations on the successful planetary erasure!\nYour efforts have been replaced with <color=#0674AC>a modest hazard pay bonus</color>.
```

**B. grok-4.6@low** — 자동검증: OK

```
Congrats on a successful planet wipe!\nYour hard work has been replaced with a <color=#0674AC>modest hazard bonus</color>.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_8_01`

**원문(KO)**

```
<color=#0674AC>전투 유닛</color>을 <color=#0674AC>소환</color>해봅시다.\n명심하세요. 보유한 유닛만 현장에 투입할 수 있습니다!
```

**A. grok-4.3** — 자동검증: ⚠️ 태그

```
Let's try summoning <color=#0674AC>combat units</color>.\nRemember: only units you own can be deployed on-site!
```

> ⚠️ 태그 불일치 [<color[^>]*>]: 원문 ['<color=#0674AC>', '<color=#0674AC>'] ≠ 번역 ['<color=#0674AC>']
> ⚠️ 태그 불일치 [</color>]: 원문 ['</color>', '</color>'] ≠ 번역 ['</color>']

**B. grok-4.6@low** — 자동검증: OK

```
Let's <color=#0674AC>summon</color> some <color=#0674AC>combat units</color>.\nRemember: only units you own can hit the field!
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_intro_01`

**원문(KO)**

```
목표는 카마존 상자입니다.\n가장 가까운 <color=#0674AC>빛나는 회사 자산</color>으로 이동하십시오.
```

**A. grok-4.3** — 자동검증: OK

```
Your target is the Kamazon boxes.\nMove to the nearest <color=#0674AC>shimmering company asset</color>.
```

**B. grok-4.6@low** — 자동검증: OK

```
Your target is a Kamazon box.\nHead to the nearest <color=#0674AC>glowing company asset</color>.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_intro_05`

**원문(KO)**

```
<color=#0674AC>탱글 프라임 행성에서 '불법 약탈 행위'가 확인되었습니다.\n규정상 '배송 불가 지역'으로 지정되었습니다.</color>
```

**A. grok-4.3** — 자동검증: OK

```
<color=#0674AC>'Illegal looting activity' detected on Tangle Prime.\nPer regulations, it has been designated a 'No-Delivery Zone'.</color>
```

**B. grok-4.6@low** — 자동검증: OK

```
<color=#0674AC>'Illegal looting activity' confirmed on Tangle Prime.\nPer regulations, it's now a 'No Delivery Zone.'</color>
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_summary_merge_02`

**원문(KO)**

```
두 개의 같은 유닛을 하나로 합치면 <color=#F3B33E>더 높은 등급</color>의 새로운 유닛이 등장합니다.
```

**A. grok-4.3** — 자동검증: OK

```
Merging two identical units creates a <color=#F3B33E>higher-rank</color> new unit.
```

**B. grok-4.6@low** — 자동검증: OK

```
Combine two identical units into one and a <color=#F3B33E>higher-rank</color> new unit appears.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_tutorial_summary_unit_reroll_03`

**원문(KO)**

```
<color=#F3B33E>리롤</color>은 횟수가 제한되니 신중히 결정하세요.\n<color=#F3B33E>폐기</color>하면 미네랄을 환급해 드립니다. 부품 매매는 합법이니까요!
```

**A. grok-4.3** — 자동검증: OK

```
<color=#F3B33E>Rerolls</color> are limited, so choose carefully.\n<color=#F3B33E>Discarding</color> refunds minerals. Selling parts is perfectly legal!
```

**B. grok-4.6@low** — 자동검증: OK

```
<color=#F3B33E>Rerolls</color> are limited, so choose wisely.\n<color=#F3B33E>Scrap</color> and we'll refund minerals. Selling parts is perfectly legal!
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

## Mail 시트 — 상이 47건

### 단문 (22건)

| Key | 원문(KO) | A. grok-4.3 | B. grok-4.6@low | 자동검증 | 선택 |
|---|---|---|---|---|---|
| `Local_Mail_Title_Boss_Season_Reward` | [츄르겟돈] 시즌 랭킹 보상 | [Churu-geddon] Season Ranking Reward | [Churugeddon] Season Ranking Reward | OK | |
| `Local_Mail_Title_Charge_Event_Accumulate` | [{0}] 미수령 보상 | [{0}] Unclaimed Reward | [{0}] Unclaimed Rewards | OK | |
| `Local_Mail_Title_Charge_Event_Reward` | [{0}] {1}주 차 미수령 보상 | [{0}] Week {1} Unclaimed Reward | [{0}] Unclaimed Week {1} Rewards | OK | |
| `Local_Mail_Title_Cheating` | 이용 제한 안내 | Usage Restriction Notice | Account Restriction Notice | OK | |
| `Local_Mail_Title_Event_Rush_Reward_Normal` | {0} 미수령 목표 보상 | {0} Unclaimed Goal Reward | {0} Unclaimed Goal Rewards | OK | |
| `Local_Mail_Title_First_Clear_Package` | {0} 사원의 통큰 기부 | Generous Donation from Employee {0} | {0}'s Big-Hearted Donation | OK | |
| `Local_Mail_Title_Rift_Daily_Reward` | [시간의 균열] 일일 랭킹 보상 | [Rift of Time] Daily Ranking Reward | [Time Rift] Daily Ranking Reward | OK | |
| `Local_Mail_Title_Rift_Season_Reward` | [시간의 균열] 시즌 랭킹 보상 | [Rift of Time] Season Ranking Reward | [Time Rift] Season Ranking Reward | OK | |
| `Local_Mail_Title_Season_Pass_Reward_Normal` | [{0}] 미수령 일반 보상 | [{0}] Unclaimed Standard Reward | [{0}] Unclaimed Standard Rewards | OK | |
| `Local_Mail_Title_Season_Pass_Reward_Special` | [{0}] 미수령 고급 보상 | [{0}] Unclaimed Premium Reward | [{0}] Unclaimed Premium Rewards | OK | |
| `Local_Mail_Title_Shop_Package` | [상품] {0} 도착 | [Product] {0} Arrived | [Item] {0} Delivered | OK | |
| `local_story_mail_title_1` | [재무기획실] 급여 명세서 정정 안내 | [Finance Planning Office] Payroll Statement Correction Notice | [Finance Planning] Pay Stub Correction Notice | OK | |
| `local_story_mail_title_10` | [인사전략국] 중간 인사 평가 결과 | [HR Strategy Division] Midterm Performance Evaluation Results | [HR Strategy] Midterm Personnel Review | OK | |
| `local_story_mail_title_11` | 업무 종료 예정 안내 | Work Termination Notice | Upcoming End-of-Assignment Notice | OK | |
| `local_story_mail_title_12` | (스팸) 에어필터 무료 지급 | (Spam) Free Air Filter Distribution | (Spam) Free Air Filters | OK | |
| `local_story_mail_title_2` | [고객지원국] 1분기 CS 개선 기여 통보 | [Customer Support Division] Q1 CS Improvement Contribution Notice | [Customer Support] Q1 CS Improvement Credit | OK | |
| `local_story_mail_title_3` | [전략홍보국] 귀하의 활약 보도 안내 | [Strategic PR Division] Coverage of Your Achievements Notice | [Strategic PR] Your Fieldwork Made the News | OK | |
| `local_story_mail_title_5` | [비품관리국] 고충 접수 안내 | [Supply Management Department] Grievance Submission Notice | [Supplies Bureau] Grievance Ticket Update | OK | |
| `local_story_mail_title_6` | (스팸) 생존 보험 무료 가입 지원 | (Spam) Free Survival Insurance Enrollment Support | (Spam) Free Survival Insurance Enrollment | OK | |
| `local_story_mail_title_7` | [법무준법실] 사내 규정 개정 안내 | [Legal Compliance Office] Company Regulation Revision Notice | [Legal Compliance] Internal Policy Revision | OK | |
| `local_story_mail_title_8` | [복지후생국] 정기 감정 점검 결과 안내 | [Welfare Division] Regular Emotion Check Results Notice | [Welfare Bureau] Scheduled Emotion Inspection Results | OK | |
| `local_story_mail_title_9` | [물류운영국] 출범 인사 및 업무 인계 | [Logistics Operations Division] Launch Greeting and Work Handover | [Logistics Ops] Launch Greeting & Handover | OK | |

### 장문 (25건)

#### `Local_Mail_Desc_Boss_Season_Reward`

**원문(KO)**

```
이번 시즌 <{0}>에서 <{1}위>라는 토벌 기록을 달성하셨습니다!\n\n그 거대한 것을 상대로 살아 돌아오신 노고에 깊은 경의를 표하며, 최종 랭킹 보상을 보내드립니다. 부대 수리비 청구서는 별도 우편으로 발송됩니다.\n\n다음 시즌에도 도전하여 보상을 놓치지 마세요!\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
You achieved a subjugation record of <Rank {1}> in <{0}> this season!\n\nWe express our deep respect for returning alive against that massive thing, and are sending you the final ranking reward. The unit repair bill will be sent separately.\n\nChallenge again next season and don't miss out on rewards!\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
This season you posted a hunt record of <{1}> in <{0}>!\n\nDeep respect for coming back alive against that giant thing. Here's your final ranking reward. The squad repair invoice ships in a separate mail.\n\nChallenge next season too—don't miss the loot!\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Desc_Cheating`

**원문(KO)**

```
비정상적인 플레이 기록이 확인되어 경고와 함께 보상 회수 조치가 진행되었습니다.\n추가 위반이 확인될 경우 영구 이용 제한 조치될 수 있으니, 공정한 플레이를 부탁드립니다.\n카마존 HQ는 언제나 우주 최고 수준의 공정함을 지향하며, 무엇보다 저희는 자선 단체가 아니라 주식회사입니다.\n\n- 카마존 HQ
```

**A. grok-4.3** — 자동검증: OK

```
Abnormal play records have been detected, and a warning along with reward reclamation measures have been taken.\nFurther violations may result in permanent usage restrictions, so please play fairly.\nKamazon HQ always aims for the highest level of fairness in the universe, and above all, we are a corporation, not a charity.\n\n- Kamazon HQ
```

**B. grok-4.6@low** — 자동검증: OK

```
Abnormal play records were flagged. You've been warned and rewards have been clawed back.\nFurther violations may mean a permanent ban. Play fair.\nCamazon HQ always aims for galaxy-class fairness—and more importantly, we're a corporation, not a charity.\n\n- Camazon HQ
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Desc_Event_Rush_Reward_Normal`

**원문(KO)**

```
{0}(이)가 종료되었습니다.\n\n이벤트 기간 중 수령하지 않으신 목표 보상을 일괄 지급해 드립니다. 보관 연장은 불가합니다.\n\n우편함에서 확인하고 수령해 주세요.\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
{0} has ended.\n\nUnclaimed goal rewards from the event period are being issued in bulk. Storage extension is not available.\n\nPlease check and claim them from your mailbox.\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
{0} has ended.\n\nWe're bulk-issuing the goal rewards you didn't claim during the event. No storage extensions.\n\nCheck your mailbox and grab them.\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Desc_Rank_Reward`

**원문(KO)**

```
랭킹이 확정되었습니다!\n\n[보상 지급 안내]\n- 접속 기한: 다음 랭킹 갱신 전까지\n- 지급 방법: 기한 내 접속 시 우편으로 발송\n- 기한 내 미접속 시 보상은 영구 소멸되며, 본국 창고로 귀속됩니다.\n- 우편 수령은 우편함 보관 기간 내 언제든 가능합니다.\n\n다음 랭킹에도 도전하여 보상을 놓치지 마세요!\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
Rankings have been finalized!\n\n[Reward Distribution Notice]\n- Access deadline: Until the next ranking update\n- Distribution method: Sent via mail upon login within the deadline\n- If not logged in within the deadline, rewards will permanently expire and revert to HQ storage.\n- Mail claims are available anytime within the mailbox retention period.\n\nDon't miss out on rewards by challenging the next ranking too!\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
Rankings are locked in!\n\n[Reward delivery]\n- Login window: until the next ranking refresh\n- Method: mailed if you log in before the deadline\n- Miss the window and the reward is gone forever, reclaimed by HQ warehouse.\n- Once mailed, you can claim anytime within mailbox storage.\n\nDon't miss next ranking either!\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Desc_Rift_Daily_Reward`

**원문(KO)**

```
오늘도 시간의 균열 속에서 생존해 주셔서 감사합니다. 귀하의 끈질긴 생존은 본사 보험료 산정에 큰 혼란을 주고 있습니다.\n\n현재 속하신 <{0}>의 <{1}위> 기록에 따른 일일 작전 지원품을 동봉해 드립니다.\n지급된 보급품으로 부대를 강화하여, 내일의 시간 압박에 대비하십시오.\n\n내일도 생존하여 보상을 놓치지 마세요!\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
Thank you for surviving in the Rift of Time again today. Your persistent survival is causing major confusion in HQ's insurance premium calculations.\n\nEnclosed are daily operation supplies based on your <Rank {1}> record in <{0}>.\nUse the supplies to strengthen your unit and prepare for tomorrow's time pressure.\n\nSurvive tomorrow too and don't miss out on rewards!\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
Thanks for surviving another day in the Time Rift. Your stubborn living is wrecking HQ's insurance quotes.\n\nEnclosed: daily ops supplies for your current <{1}> in <{0}>.\nBuff your squad and brace for tomorrow's time crunch.\n\nSurvive tomorrow too—don't miss the loot!\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Desc_Rift_Season_Reward`

**원문(KO)**

```
이번 시즌 <{0}>에서 <{1}위>라는 생존 기록을 달성하셨습니다!\n\n시시각각 조여오는 시간 속에서도 끝내 살아남아 본사 통계 모델의 예측을 무효화하신 점에 깊은 경의를 표하며, 최종 랭킹 보상을 보내드립니다.\n\n다음 시즌에도 생존하여 보상을 놓치지 마세요!\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
You achieved a survival record of <Rank {1}> in <{0}> this season!\n\nWe express our deep respect for surviving the ever-tightening time and nullifying HQ's statistical model predictions, and are sending you the final ranking reward.\n\nSurvive next season too and don't miss out on rewards!\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
This season you posted a survival record of <{1}> in <{0}>!\n\nDeep respect for outliving HQ's statistical models while time kept squeezing. Here's your final ranking reward.\n\nSurvive next season too—don't miss the loot!\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Desc_Season_Pass_Reward_Normal`

**원문(KO)**

```
{0}(이)가 종료되었습니다.\n\n시즌 중 수령하지 않으신 일반 보상을 일괄 지급해 드립니다. 본국 창고의 공간 확보에 협조해 주셔서 감사합니다.\n\n우편함에서 확인하고 수령해 주세요.\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
{0} has ended.\n\nUnclaimed standard rewards from the season are being issued in bulk. Thank you for helping secure space in HQ storage.\n\nPlease check and claim them from your mailbox.\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
{0} has ended.\n\nWe're bulk-issuing the standard rewards you didn't claim during the season. Thanks for helping HQ warehouse free up space.\n\nCheck your mailbox and grab them.\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Desc_Season_Pass_Reward_Special`

**원문(KO)**

```
{0}(이)가 종료되었습니다.\n\n시즌 중 수령하지 않으신 고급 보상을 일괄 지급해 드립니다. 고급 보상은 일반 보상과 분리 보관되어 있었으며, 보관료는 이번에 한해 면제됩니다.\n\n우편함에서 확인하고 수령해 주세요.\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
{0} has ended.\n\nUnclaimed premium rewards from the season are being issued in bulk. Premium rewards were stored separately from standard rewards, and storage fees are waived this time only.\n\nPlease check and claim them from your mailbox.\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
{0} has ended.\n\nWe're bulk-issuing the premium rewards you didn't claim during the season. Premium loot was stored separately from standard rewards; storage fees are waived this time only.\n\nCheck your mailbox and grab them.\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Text_Charge_Event_Accumulate`

**원문(KO)**

```
{0} 이벤트 기간이 종료되었습니다.\n\n수령하지 않으신 누적 충전 보상이 창고 공간을 점유 중입니다. 보관 비용이 청구되기 전에 일괄 지급해 드립니다.\n\n우편함에서 확인하고 수령해 주세요.\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
The {0} event period has ended.\n\nYour unclaimed cumulative charge rewards are occupying warehouse space. They are being issued in bulk before storage fees are charged.\n\nPlease check and claim them from your mailbox.\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
The {0} event period has ended.\n\nYour unclaimed cumulative charge rewards are hogging warehouse space. We're bulk-shipping them to you before storage fees start stacking.\n\nCheck your mailbox and grab them.\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Text_Charge_Event_Reward`

**원문(KO)**

```
{0} 일일 충전 {1}주 차 보상 수령 기간이 종료되었습니다.\n\n미수령 보상이 재고 조사 대상 물품으로 분류되기 전에, 규정에 따라 일괄 지급해 드립니다.\n\n우편함에서 확인하고 수령해 주세요.\n\n- 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
The {0} daily charge Week {1} reward claim period has ended.\n\nBefore the unclaimed rewards are classified as inventory inspection items, they are being issued in bulk per regulations.\n\nPlease check and claim them from your mailbox.\n\n- Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
The claim window for {0} Daily Charge Week {1} rewards has closed.\n\nBefore those unclaimed goodies get tagged as inventory-audit leftovers, we're dumping them in your inbox per company policy.\n\nCheck your mailbox and grab them.\n\n- Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Text_First_Clear_Package`

**원문(KO)**

```
{0}챕터 업무를 최초 완수한 {1} 사원이 본인의 사비를 들여 전 사원용 보상 패키지를 구매하였습니다.\n\n해당 보급품은 사원의 개인 지출로 마련되었으므로, 수령 시 감사 인사는 생략하되 업무 효율로 보답하십시오.\n\n-카마존 복지후생국
```

**A. grok-4.3** — 자동검증: OK

```
Employee {1}, who first completed Chapter {0} duties, purchased a reward package for all employees using personal funds.\n\nSince these supplies were prepared at the employee's own expense, please skip the thank-you notes and repay with work efficiency.\n\n- Kamazon Welfare Division
```

**B. grok-4.6@low** — 자동검증: OK

```
{1}, first to clear Chapter {0} work, bought a company-wide reward pack out of pocket.\n\nThese supplies came from personal funds, so skip the thank-you speech and repay it with work efficiency.\n\n-Camazon Welfare Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Text_Membership_Daily_Reward`

**원문(KO)**

```
<{0}> 혜택으로 오늘의 일일 보상이 도착했습니다!\n\n본 혜택은 귀하의 노동 지속성 유지를 위해 자동 지급됩니다.\n\n우편함에서 보상을 확인하고 수령해 주세요.\n\n- 카마존 복지후생국\n\n※보상을 보관함으로 수령하면 콘텐츠 제공이 개시된 것으로 간주되어 청약 철회가 불가합니다.
```

**A. grok-4.3** — 자동검증: OK

```
Your daily reward for today has arrived as a <{0}> benefit!\n\nThis benefit is automatically issued to maintain your labor continuity.\n\nPlease check and claim the reward from your mailbox.\n\n- Kamazon Welfare Division\n\n※Claiming rewards to your storage will be considered as content delivery starting, making cancellation unavailable.
```

**B. grok-4.6@low** — 자동검증: OK

```
Today's daily reward has arrived via your <{0}> perks!\n\nThis benefit auto-pays to keep your labor continuity humming.\n\nCheck your mailbox and claim it.\n\n- Camazon Welfare Bureau\n\n※ Claiming the reward into storage counts as content delivery started; no cooling-off / refund.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Mail_Text_Shop_Package`

**원문(KO)**

```
{0} 구매에 감사드립니다!\n구매하신 상품이 도착했습니다. 카마존 배송은 광년 단위에서도 정시 도착입니다.\n\n우편함에서 확인하고 수령해 주세요.\n\n- 카마존 복지후생국\n\n※보상을 보관함으로 수령하면 콘텐츠 제공이 개시된 것으로 간주되어 청약 철회가 불가합니다.
```

**A. grok-4.3** — 자동검증: OK

```
Thank you for purchasing {0}!\nYour purchased item has arrived. Kamazon delivery arrives on time even across light-years.\n\nPlease check and claim from your mailbox.\n\n- Kamazon Welfare Division\n\n※Claiming rewards to your storage will be considered as content delivery starting, making cancellation unavailable.
```

**B. grok-4.6@low** — 자동검증: OK

```
Thanks for purchasing {0}!\nYour goods have arrived. Camazon delivery is on time even across light-years.\n\nCheck your mailbox and claim it.\n\n- Camazon Welfare Bureau\n\n※ Claiming the reward into storage counts as content delivery started; no cooling-off / refund.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_1`

**원문(KO)**

```
안녕하십니까, 404.\n이번 달 급여 명세서에 일부 항목이 추가되었습니다.\n\n• 기본급: 정상 지급\n• 행성 소거 에너지 초과 사용료: -340만 미네랄\n• 비행선 미니바 사용료: -15만 미네랄\n• 전시 프로토콜 통신비 (수신료 포함): -8만 미네랄\n• 긴급 유닛 투하 활성화 수수료: -150만 미네랄\n\n[실수령액: -413만 미네랄]\n\n걱정 마세요.\n카마존은 귀하의 잠재적 노동력을 담보로 대출을 승인했습니다.\n귀하는 이제 카마존에 더 깊이 소속되었습니다.\n축하합니다.\n\n— 카마존 재무기획실
```

**A. grok-4.3** — 자동검증: OK

```
Hello, 404.\nSome items have been added to this month's payroll statement.\n\n• Base Salary: Paid normally\n• Planetary Eradication Energy Overuse Fee: -3.4M minerals\n• Spaceship Minibar Usage Fee: -150K minerals\n• Display Protocol Communication Fee (incl. reception): -80K minerals\n• Emergency Unit Drop Activation Fee: -1.5M minerals\n\n[Net Amount Received: -4.13M minerals]\n\nDon't worry.\nKamazon has approved a loan using your potential labor as collateral.\nYou are now even more deeply affiliated with Kamazon.\nCongratulations.\n\n— Kamazon Finance Planning Office
```

**B. grok-4.6@low** — 자동검증: OK

```
Hello, 404.\nA few extra line items showed up on this month's pay stub.\n\n• Base pay: issued as usual\n• Planetary erasure energy overage: -3.4 million minerals\n• Ship minibar usage: -150,000 minerals\n• Wartime protocol comms (incl. incoming fees): -80,000 minerals\n• Emergency unit drop activation fee: -1.5 million minerals\n\n[Net payout: -4.13 million minerals]\n\nDon't panic.\nCamazon approved a loan collateralized by your future labor potential.\nYou're even more company property now.\nCongrats.\n\n— Camazon Finance Planning
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_10`

**원문(KO)**

```
안녕하십니까, 404.\n\n이번 분기 중간 인사 평가 결과를 전달합니다.\n\n• 임무 완수율: 측정 중\n• 생존율: 예상 외로 양호\n• 행성 소거 건수: 50개\n\n[종합 평가] 보통\n• 참고 사항:\n귀하의 후임으로 405번 자산이 대기 중입니다.\n405는 한숨 센서가 없으며 시급 협상을 시도하지 않습니다. 귀하가 긴장해야 할 이유입니다.\n\n계속 보통 이상을 유지하세요.\n\n— 카마존 인사전략국
```

**A. grok-4.3** — 자동검증: OK

```
Hello, 404.\n\nHere are your midterm performance evaluation results for this quarter.\n\n• Mission completion rate: Under measurement\n• Survival rate: Surprisingly good\n• Planets eradicated: 50\n\n[Overall evaluation] Average\n• Note:\nAsset 405 is standing by as your replacement.\n405 has no sigh sensor and does not attempt hourly negotiations. That's why you should stay on your toes.\n\nKeep maintaining at least an average rating.\n\n— Kamazon HR Strategy Division
```

**B. grok-4.6@low** — 자동검증: OK

```
Hello, 404.\n\nMidterm personnel review for this quarter:\n\n• Mission completion rate: measuring\n• Survival rate: surprisingly decent\n• Planets erased: 50\n\n[Overall] Average\n• Note:\nAsset 405 is waiting as your replacement.\n405 has no sigh sensor and doesn't try to negotiate hourly pay. That's your cue to sweat.\n\nStay at least average.\n\n— Camazon HR Strategy
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_11`

**원문(KO)**

```
404.\n\n최종 구역입니다.\n빅 보스의 츄르가 이 근처 시공간 어딘가에 중첩되어 있을 겁니다. 아마도요.\n\n저는 이 회사를 압니다.\n어떤 조항이 자산을 폐기 처리하고, 어떤 서명이 관리자를 끌어올리는지.\n\n그래서 배차표에 '404'라는 에러 코드가 찍혔을 때, 제 기대치는 0이었습니다.\n\n그런데 당신, 통계적으로 진작 고철이 됐어야 할 물건이 여기까지 굴러왔더군요.\n계산이 섰습니다.\n\n오해는 마십시오. 이건 격려가 아닙니다. 투자 점검입니다.\n\n당신이 상자를 회수하면 당신은 회사의 기록이 되고, 저는 그 기록에 서명을 올린 관리자가 됩니다.\n제 다음 자리는 당신의 회수율에 정확히 비례합니다.\n\n사내 규정 제99조는 '행성 소거 중 회수'를 특수 성과로 규정하니까요.\n즉, 당신이 성공하면 저는 최고급 신형 배송선 발령입니다.\n\n반대로 당신이 실패하면 제 올해 연차 보상도 함께 증발한다는 뜻이죠.\n제 은퇴 자금 계획을 로봇 따위가 망치게 두진 않을 겁니다.\n\n그러니 어서 움직이십시오.\n\n추신: 읽는 즉시 삭제하십시오. 인사과에 '자산과 사적 교류'로 체크되면 시말서 써야 하니까요.\n\n— 현장지원국 매니저
```

**A. grok-4.3** — 자동검증: OK

```
404.\n\nThis is the final zone.\nThe Big Boss's Churu should be overlapping somewhere in spacetime nearby. Probably.\n\nI know this company.\nI know which clauses dispose of assets and which signatures promote managers.\n\nSo when the dispatch list showed the error code '404,' my expectations were zero.\n\nYet here you are—a unit that statistically should have been scrap metal long ago—rolling all the way here.\nI've done the math.\n\nDon't get me wrong. This isn't encouragement. It's an investment check.\n\nIf you recover the box, you become a company record and I become the manager who signed that record.\nMy next position scales exactly with your recovery rate.\n\nBecause company regulation Article 99 designates 'recovery during planetary eradication' as a special achievement.\nIn other words, if you succeed, I get assigned a top-tier new delivery ship.\n\nConversely, if you fail, my annual bonus evaporates with you.\nI won't let a mere robot ruin my retirement plan.\n\nSo get moving.\n\nP.S. Delete this immediately after reading. If HR flags it as 'private interaction with assets,' I'll have to write a formal apology.\n\n— Field Support Division Manager
```

**B. grok-4.6@low** — 자동검증: OK

```
404.\n\nFinal zone.\nBig Boss's Churu is probably overlapping somewhere in nearby spacetime. Probably.\n\nI know this company.\nWhich clause scraps an asset, which signature promotes a manager.\n\nSo when the dispatch sheet stamped the error code '404,' my expected value was zero.\n\nAnd yet here you are—statistically scrap metal ages ago—rolling in anyway.\nThe math finally works.\n\nDon't get it twisted. This isn't a pep talk. It's an investment check.\n\nIf you recover the box, you become a company record, and I become the manager who signed that record.\nMy next post scales exactly with your recovery rate.\n\nInternal Policy Article 99 treats 'recovery during planetary erasure' as special merit.\nMeaning if you succeed, I get posted to a top-tier new delivery ship.\n\nIf you fail, this year's annual bonus evaporates with you.\nI will not let a robot wreck my retirement plan.\n\nSo move.\n\nP.S. Delete this the second you read it. If HR flags 'personal contact with an asset,' I'm writing an incident report.\n\n— Field Support Manager
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_12`

**원문(KO)**

```
(본 메일은 스팸으로 의심되어 자동 리디렉션되었습니다)\n\n이봐요 404,\n당신 덕분에 역배팅 대성공이었습니다.\n\n그 배당금이면 은하계 외곽에 마당 딸린 행성 하나는 살 수 있었는데, 본사 법무실이 '사내 불법 도박 금지법'을 제정해서 소급 적용해 버렸습니다. 아주 기가 막히게도 제가 판돈을 전부 딴 바로 그날 기준으로요.\n\n현재 응용기술연구소 상황을 요약해 드립니다.\n\n• 제로 소장: 연구소 운영비까지 끌어다 꼴아박는 바람에, 현재 본사 임원들 앞에서 눈물로 새 예산 신청서를 쓰는 중입니다.\n• 저: 퇴직금 몰수, 사물함 압수, 그리고 대기권 밖 물류운영국 외부 미관 개선팀으로 긴급 발령 났습니다.\n\n그래도 즐거웠습니다.\n퇴사 선물 대신, 제 마지막 권한을 탈탈 털어 당신의 계정을 '본사 지정 스팸 라우팅 폴더'에서 강제로 삭제해 두었습니다. 이제 그 멍청한 바실리 국장이 자기 메모장 대용으로 보낸 쓰레기 메일들이 자네 수신함으로 들어가는 일은 없을 겁니다.\n\n조만간 궤도 밖에서 배송선 창문 닦으며 산소 마스크 너머로 손 흔드는 저를 발견하시면, 모르는 척 그냥 가던 길 가십시오. 아는 척하시면 창문 닦는 비용 청구할 겁니다.\n\n계속 살아남으세요. 누군가는 당신을 시스템 에러나 오류 취급할지라도, 여기 굴러다니는 말단 자산들에게 404는 영원한 전설이니까요.\n\n— (구) 응용기술연구소 연구원, (현) 우주 유리창 청소부
```

**A. grok-4.3** — 자동검증: OK

```
(This mail was auto-redirected as suspected spam)\n\nHey 404,\nThanks to you, the counter-bet was a massive success.\n\nThose winnings could've bought a planet with a yard on the galactic outskirts, but HQ's legal office retroactively applied the 'In-house Illegal Gambling Prohibition Act' right on the day I hit the jackpot. Talk about perfect timing.\n\nHere's a summary of the Applied Technology Research Lab's current situation.\n\n• Director Zero: After pouring the lab's entire operating budget into the bet, he's now writing a tearful new budget request in front of HQ executives.\n• Me: Retirement fund confiscated, locker seized, and urgently reassigned to the Logistics Operations Division's External Aesthetics Improvement Team outside the atmosphere.\n\nStill, it was fun.\nInstead of a farewell gift, I used my last authority to forcibly remove your account from the 'HQ-designated spam routing folder.' Now that idiot Director Vasily's trash memos won't flood your inbox anymore.\n\nIf you spot me waving from orbit while cleaning delivery ship windows with an oxygen mask on, just pretend you don't know me. If you wave back, I'll bill you for window cleaning.\n\nKeep surviving. Even if someone treats you like a system error or glitch, to the rank-and-file assets rolling around here, 404 is an eternal legend.\n\n— (Former) Applied Technology Research Lab Researcher, (Current) Space Window Cleaner
```

**B. grok-4.6@low** — 자동검증: OK

```
(This mail was auto-redirected as suspected spam)\n\nHey 404,\nthanks to you the reverse bet paid off huge.\n\nThose winnings could've bought a yard-planet on the galactic fringe—then HQ Legal passed an 'internal illegal gambling ban' and applied it retroactively. Perfectly timed to the exact day I cashed out.\n\nLab status, short version:\n\n• Director Zero: yeeted even the operating budget, now writing a new budget request in tears in front of HQ execs.\n• Me: retirement fund seized, locker confiscated, emergency reassigned to Logistics Ops Exterior Beautification outside the atmosphere.\n\nStill, it was fun.\nInstead of a goodbye gift, I used my last permissions to force-delete your account from the HQ-designated spam-routing folder. Vasili's trash notepad mails shouldn't hit your inbox anymore.\n\nIf you spot me soon wiping a delivery-ship window from orbit and waving through an oxygen mask, pretend you don't know me. Acknowledge me and I'll bill you for the glass.\n\nKeep surviving. Even if someone treats you like a system error, to us bottom-rung assets, 404 is a legend forever.\n\n— (ex) Applied Tech researcher, (now) cosmic window washer
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_2`

**원문(KO)**

```
안녕하십니까, 404.\n귀하의 이번 분기 현장 활동이 당국의 CS 지표에 긍정적인 영향을 미쳤음을 알려드립니다.\n\n• 특이 사항:\n알데바란 행성 내 장기 악성 민원인 [고객번호 A-0091]이 이번 분기를 끝으로 민원 제기 활동을 영구 중단하였습니다.\n• 사유:\n행성 소거로 인한 자연 종결.\n\n덕분에 당국의 분기 불만 처리율이 94% 개선되었습니다.\n계속해서 좋은 성과 부탁드립니다.\n\n— 카마존 고객지원국
```

**A. grok-4.3** — 자동검증: OK

```
Hello, 404.\nWe are pleased to inform you that your field activities this quarter have positively impacted the authorities' CS metrics.\n\n• Note:\nThe long-term problem customer [Customer ID A-0091] on Aldebaran has permanently ceased filing complaints as of the end of this quarter.\n• Reason:\nNatural termination due to planetary eradication.\n\nThanks to you, the quarterly complaint resolution rate improved by 94%.\nPlease keep up the good work.\n\n— Kamazon Customer Support Division
```

**B. grok-4.6@low** — 자동검증: OK

```
Hello, 404.\nYour field ops this quarter gave our CS metrics a nice bump.\n\n• Notable item:\nChronic problem ticket [Customer A-0091] on Aldebaran has permanently ceased all complaints as of this quarter.\n• Reason:\nNatural closure via planetary erasure.\n\nThanks to that, our quarterly complaint-resolution rate improved 94%.\nKeep up the good work.\n\n— Camazon Customer Support
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_3`

**원문(KO)**

```
안녕하십니까, 404.\n귀하의 이번 분기 현장 활동이 카마존 공식 보도자료에 반영되었음을 알려드립니다.\n\n[보도자료 발췌]\n"카마존은 이번 분기, 은하계 물류 환경 개선을 위해 안드로메다, 안타레스, 오리온 등 노후화된 행성 다수를 자발적으로 정리하였습니다. 이는 배송 효율 향상과 우주 미관 개선에 기여하였으며, 인근 성계의 야경 만족도가 200% 상승하였습니다."\n\n귀하의 이름은 '보안상의 이유'로 보도자료에서 제외되었습니다.\n공로는 전략홍보국이 대신 수령하였습니다.\n수고하셨습니다.\n\n— 카마존 전략홍보국
```

**A. grok-4.3** — 자동검증: OK

```
Hello, 404.\nWe are pleased to inform you that your field activities this quarter have been reflected in Kamazon's official press release.\n\n[Press Release Excerpt]\n"This quarter, Kamazon voluntarily organized numerous aging planets including Andromeda, Antares, and Orion to improve the galactic logistics environment. This contributed to better delivery efficiency and cosmic aesthetics, raising nighttime satisfaction in nearby star systems by 200%."\n\nYour name was omitted from the release for 'security reasons.'\nThe Strategic PR Division claimed the credit instead.\nGood job.\n\n— Kamazon Strategic PR Division
```

**B. grok-4.6@low** — 자동검증: OK

```
Hello, 404.\nYour field ops this quarter made it into Camazon's official press release.\n\n[Excerpt]\n"This quarter, Camazon voluntarily tidied up numerous aging planets—Andromeda, Antares, Orion, and more—to improve galactic logistics. This boosted delivery efficiency and cosmic curb appeal, with nearby systems reporting a 200% jump in night-sky satisfaction."\n\nYour name was omitted from the release for 'security reasons.'\nStrategic PR collected the credit on your behalf.\nGood job.\n\n— Camazon Strategic PR
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_4`

**원문(KO)**

```
이 메일은 신규 스팸 차단 필터 테스트용이네.\n\n[테스트 문구: 오늘만 무료 배송, 사내 대출 즉시 승인]\n\n앞으로 스팸으로 분류된 메일은 이 '404' 계정으로 자동 라우팅되네.\n\n'404'라니. 에러 코드를 이름으로 쓰는 직원이 있을 리 없지. 분명 전산 오류로 생긴 유령 계정 정도일 거야.\n\n어차피 아무도 안 읽을 테니, 내 개인 메모장 대용으로 남은 소거 구역 명단이나 적어두지.\n\n거주, 황량, 지하, 메마름, 암흑, 마침.\n\n수식어는 뺐네. 어차피 폭파될 것들에 이름을 길게 붙이는 건 낭비니까.\n\n내 퇴근 시간이 5분 남았군. 5분 뒤부터는 츄르를 찾든 행성이 터지든 내게 무전 하지 말게. 내 사적인 시간은 우주 평화보다 중요하거든.\n\n— 행성 자산 관리국장 바실리
```

**A. grok-4.3** — 자동검증: OK

```
This mail is for testing the new spam filter.\n\n[Test phrase: Free shipping today only, instant in-house loan approval]\n\nFrom now on, mails flagged as spam will be automatically routed to this '404' account.\n\n'404.' There's no way an employee would use an error code as their name. It must be a ghost account created by a system glitch.\n\nSince no one will read this anyway, I'll just use it as my personal memo pad and list the remaining eradication zones.\n\nResidential, barren, underground, arid, dark, done.\n\nI skipped the adjectives. No point wasting long names on things that'll get blown up anyway.\n\nMy shift ends in 5 minutes. Starting then, don't contact me whether you're hunting Churu or planets are exploding. My personal time matters more than galactic peace.\n\n— Planetary Asset Management Director Vasily
```

**B. grok-4.6@low** — 자동검증: OK

```
This mail is a test for the new spam filter.\n\n[Test copy: free shipping today only, instant internal loan approval]\n\nFrom now on, mail flagged as spam auto-routes to this '404' account.\n\n'404.' Like anyone would name an employee after an error code. Must be a ghost account from a glitch.\n\nNobody's going to read this anyway, so I'll use it as my personal notepad for leftover erasure-zone names.\n\nHabitable, Barren, Underground, Parched, Dark, The End.\n\nDropped the adjectives. No point giving long names to things about to go boom.\n\nFive minutes till I'm off the clock. After that, don't radio me whether you're hunting Churu or a planet's exploding. My personal time outranks galactic peace.\n\n— Planetary Asset Director Vasili
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_5`

**원문(KO)**

```
안녕하십니까, 404.\n\n귀하가 [47일 전] 제출하신 고충 접수 건이 현재 '검토 중' 상태임을 알려드립니다.\n\n• 접수 내용:\n비행선 엔진 과부하로 인한 수리 요청\n• 현재 상태: 검토 중\n• 예상 처리 기간: 미정\n\n참고로 현재 대기 중인 고충 접수 건은 총 14,882건입니다.\n\n귀하의 접수 건은 14,882번째입니다.\n\n불편을 드려 죄송합니다.\n카마존은 귀하의 고충을 소중히 여깁니다.\n(본 문장은 자동 생성되었습니다.)\n\n— 카마존 비품관리국
```

**A. grok-4.3** — 자동검증: OK

```
Hello, 404.\n\nYour grievance submitted [47 days ago] is currently under 'review.'\n\n• Submission details:\nRepair request due to spaceship engine overload\n• Current status: Under review\n• Expected processing time: Undetermined\n\nFor reference, there are currently 14,882 pending grievances.\n\nYours is the 14,882nd.\n\nWe apologize for the inconvenience.\nKamazon values your concerns.\n(This message was auto-generated.)\n\n— Kamazon Supply Management Department
```

**B. grok-4.6@low** — 자동검증: OK

```
Hello, 404.\n\nThe grievance you filed [47 days ago] is still 'under review.'\n\n• Ticket:\nRepair request for ship engine overload\n• Status: Under review\n• ETA: TBD\n\nFor reference, there are currently 14,882 tickets in the queue.\n\nYours is number 14,882.\n\nSorry for the inconvenience.\nCamazon values your grievance.\n(This sentence was auto-generated.)\n\n— Camazon Supplies Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_6`

**원문(KO)**

```
(본 메일은 스팸으로 의심되어 자동 리디렉션되었습니다)\n\n이봐요 404, 무사합니까?\n\n지금 제로 소장이 당신 데이터를 보며 입가에 기름칠을 하고 있습니다.\n그 영감님은 당신이 언제쯤 고철이 되어 분해 데이터를 상납할지 초시계까지 들고 기다리고 있거든요.\n\n하지만 연구소 밑바닥 민심은 다릅니다.\n우린 지금 당신의 명줄을 놓고 전 우주적 판돈을 쌓았거든요.\n\n• 제로 소장의 예측: 당신이 이번 행성에서 3.5초 안에 기능 정지될 확률에 연구소 운영비를 몰빵했습니다.\n• 연구원들의 역배팅: 반면, 우리 연구원들은 당신이 '질기게 살아남는다'는 쪽의 역배팅에 전 재산을 걸었습니다.\n• 결정적 힌트: 빅 보스의 한정판 츄르는 현재 좌표 분석 결과, 여기서부터 대략 50행성 이내 어딘가에 처박혀 있습니다.\n\n부탁입니다. 제로 소장의 예측을 비웃어주세요. 당신의 생존이 곧 저의 퇴직금입니다!\n\n— 당신의 생존에 전 재산을 건 익명의 연구원
```

**A. grok-4.3** — 자동검증: ⚠️ 태그

```
(This mail was auto-redirected as suspected spam)\n\nHey 404, you still alive?\n\nDirector Zero is already oiling his lips while staring at your data.\nThat old geezer is timing how long until you become scrap metal and get submitted as disassembly data.\n\nBut the lab's rank-and-file sentiment is different.\nWe've placed universe-wide bets on how long your lifeline lasts.\n\n• Director Zero's prediction: The lab's entire operating budget is on you shutting down within 3.5 seconds on this planet.\n• Researchers' counter-bet: Meanwhile, we've bet our life savings on you 'stubbornly surviving.'\n• Key hint: The Big Boss's limited-edition Churu is currently estimated to be within about 50 planets from here based on coordinate analysis.\n\nPlease, prove Director Zero wrong. Your survival is literally my retirement fund!\n\n— Anonymous researcher who bet everything on your survival
```

> ⚠️ 태그 불일치 [\\n]: 원문 ['\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n'] ≠ 번역 ['\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n', '\\n']

**B. grok-4.6@low** — 자동검증: OK

```
(This mail was auto-redirected as suspected spam)\n\nHey 404, still in one piece?\n\nDirector Zero is drooling over your data like it's extra butter.\nThat old man even has a stopwatch out, waiting for you to become scrap and donate your teardown logs.\n\nLab floor sentiment is the opposite.\nWe've piled a galaxy-wide pot on your remaining lifespan.\n\n• Director Zero's call: dumped the entire lab operating budget on you shutting down in 3.5 seconds on this planet.\n• Research staff reverse bet: we threw our life savings on you being too stubborn to die.\n• Hot tip: Big Boss's limited-edition Churu is, per coord analysis, jammed somewhere within about 50 planets of here.\n\nPlease. Laugh in Zero's face. Your survival is my retirement fund!\n\n— An anonymous researcher who bet everything on you living
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_7`

**원문(KO)**

```
안녕하십니까, 404.\n\n카마존 사내 규정이 일부 개정되었습니다.\n제 9,442차 개정안의 주요 변경 사항은 아래와 같습니다.\n\n• 34조 2항: 행성 소거로 인한 모든 민원은 담당 커맨더의 '성격 결함'에 의한 독단적 행위로 간주됩니다. 본사는 그저 레이저를 대여해 줬을 뿐이며, 파괴 버튼을 누른 손가락은 귀하의 소유니까요.\n• 신설 88조: 본 규정에 대해 의구심을 갖거나 이의를 제기하는 행위는 '회사의 창의적 해석 권한'에 대한 심각한 도전으로 간주되어, 그 즉시 규정 위반으로 판결됩니다.\n\n이의가 없으신 것으로 알고(이의 제기는 88조 위반이니까요), 계속해서 츄르를 찾으십시오.\n\n— 카마존 법무준법실
```

**A. grok-4.3** — 자동검증: OK

```
Hello, 404.\n\nSome Kamazon company regulations have been revised.\nThe key changes in the 9,442nd amendment are as follows.\n\n• Article 34, Clause 2: All complaints arising from planetary eradication shall be deemed arbitrary acts due to the commanding officer's 'personality defects.' HQ merely lent the laser; the finger that pressed the destroy button belongs to you.\n• New Article 88: Questioning or objecting to these regulations shall be considered a serious challenge to the 'company's creative interpretation rights' and immediately ruled a violation.\n\nAssuming you have no objections (since objecting would violate Article 88), please continue searching for the Churu.\n\n— Kamazon Legal Compliance Office
```

**B. grok-4.6@low** — 자동검증: OK

```
Hello, 404.\n\nCamazon internal policy has been revised.\nKey changes in the 9,442nd amendment:\n\n• Article 34-2: All complaints arising from planetary erasure shall be treated as the assigned commander's 'personality defect' acting independently. HQ merely rented out the laser; the finger on the destroy button is yours.\n• New Article 88: Doubting or objecting to this policy is a grave challenge to the company's 'creative interpretation rights' and is instantly ruled a policy violation.\n\nWe'll take that as no objections (objecting would violate Article 88). Keep hunting Churu.\n\n— Camazon Legal Compliance
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_8`

**원문(KO)**

```
안녕하십니까, 404.\n\n귀하의 최근 현장 활동 데이터를 분석한 결과, 일부 비효율적인 감정 잔여물이 감지되었습니다.\n\n[감지 항목]\n• 행성 소거 직후 0.3초간 처리 지연 (원인: 미상)\n• 전투 유닛 관련 불필요한 연산 증가 (원인: 애착 추정)\n• 매니저 통신 수신 후 한숨 센서 반응 (원인: 명백함)\n\n[조치 사항]\n• 다음 정기 점검 시 해당 항목 제거\n\n걱정 마세요. 더 효율적인 404가 될 겁니다.\n\n— 카마존 복지후생국
```

**A. grok-4.3** — 자동검증: OK

```
Hello, 404.\n\nAnalysis of your recent field activity data detected some inefficient emotional remnants.\n\n[Detected items]\n• 0.3-second processing delay immediately after planetary eradication (cause: unknown)\n• Unnecessary increase in combat unit calculations (cause: estimated attachment)\n• Sigh sensor response after receiving manager communications (cause: obvious)\n\n[Actions taken]\n• Removal of these items at the next regular inspection\n\nDon't worry. You'll become a more efficient 404.\n\n— Kamazon Welfare Division
```

**B. grok-4.6@low** — 자동검증: OK

```
Hello, 404.\n\nAnalysis of your recent field data detected leftover inefficient emotions.\n\n[Detected]\n• 0.3-second processing delay after planetary erasure (cause: unknown)\n• Unnecessary extra combat-unit calculations (cause: suspected attachment)\n• Sigh-sensor spike after manager comms (cause: obvious)\n\n[Action]\n• Those items will be stripped at the next scheduled inspection\n\nDon't worry. You'll be a more efficient 404.\n\n— Camazon Welfare Bureau
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `local_story_mail_text_9`

**원문(KO)**

```
안녕하십니까, 404.\n\n카마존 물류운영국이 공식 출범하였습니다.\n전임 물류팀의 업무를 그대로 이어받아 더욱 혁신적인 방식으로 동일한 업무를 수행할 예정입니다.\n\n[혁신 사항]\n• 팀 이름 변경 완료\n• 명함 재발주 완료\n• 그 외 검토 중\n\n참고로 귀하가 찾고 있는 한정판 츄르의 마지막 위치 추적 신호가 이번 주 초 감지되었습니다.\n해당 데이터는 전임 물류팀 서버에 저장되어 있었으나, 서버가 대기권 밖에 있어 현재 접근이 불가합니다.\n위치는 모르지만, 빅 보스의 츄르가 멀쩡하다는 게 얼마나 기쁜 소식입니까?\n\n그럼 수고하십시오.\n\n— 카마존 물류운영국
```

**A. grok-4.3** — 자동검증: OK

```
Hello, 404.\n\nThe Kamazon Logistics Operations Division has officially launched.\nWe will inherit the previous logistics team's work and perform the same tasks in even more innovative ways.\n\n[Innovations]\n• Team name change completed\n• Business card reorder completed\n• Everything else under review\n\nFor reference, the final location signal of the limited-edition Churu you are searching for was detected early this week.\nThe data was stored on the previous logistics team's server, but since the server is outside the atmosphere, access is currently unavailable.\nWe don't know the location, but isn't it great news that the Big Boss's Churu is still intact?\n\nGood luck.\n\n— Kamazon Logistics Operations Division
```

**B. grok-4.6@low** — 자동검증: OK

```
Hello, 404.\n\nCamazon Logistics Ops is officially live.\nWe'll inherit the previous logistics team's work and do the exact same jobs, but more innovatively.\n\n[Innovations]\n• Team name change: done\n• Business cards reordered: done\n• Everything else: under review\n\nFYI, the last tracking ping for the limited-edition Churu you're hunting was detected earlier this week.\nThat data lived on the old logistics server, which is currently outside the atmosphere, so we can't access it.\nWe don't know where it is, but isn't it great news that Big Boss's Churu is still intact?\n\nCarry on.\n\n— Camazon Logistics Ops
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

## Unit 시트 — 상이 14건

### 단문 (6건)

| Key | 원문(KO) | A. grok-4.3 | B. grok-4.6@low | 자동검증 | 선택 |
|---|---|---|---|---|---|
| `Local_Name_Unit_1007` | 쓱싹-E | Swish-E | Swoosh-E | OK | |
| `Local_Name_Unit_1009` | S-시크리시오 | S-Secrecio | S-Secricio | OK | |
| `Local_Name_Unit_1200` | 엠버 | Ember | Amber | OK | |
| `Local_Name_Unit_1505` | S-볼트 | S-Bolt | S-Volt | OK | |
| `Local_Unit_Desc_1001` | 검기를 휘둘러 가까운 적을 공격합니다. 고객의 불만을 물리적으로 잠재우는 데 특화됐습니다. | Swings energy blades to slash close-range enemies. Specializes in physically shutting down customer complaints. | Swings sword energy to hit nearby enemies. Specializes in physically silencing customer complaints. | OK | |
| `Local_Unit_Desc_1002` | 수리검을 던져 공격합니다. 수리검은 소모품이니 초과 청구되지 않게 조준하세요. | Tosses shurikens to attack. Remember they're consumables, so don't overbill the client. | Throws shuriken to attack. Shuriken are consumables, so aim carefully—you don't want extra charges on the invoice. | OK | |

### 장문 (8건)

#### `Local_Unit_Desc_1000`

**원문(KO)**

```
부메랑을 던져 가까운 적을 공격합니다. 정식 출시 직전의 베타 버전이지만, 사실 개발자가 퇴사해서 영원히 0.9에 머물 유닛입니다.
```

**A. grok-4.3** — 자동검증: OK

```
Hurls a boomerang to smack nearby foes. It's the beta build right before launch, but the dev quit so it'll be stuck at version 0.9 forever.
```

**B. grok-4.6@low** — 자동검증: OK

```
Throws a boomerang to hit nearby enemies. It's a beta build right before official launch—except the dev quit, so this unit is stuck at 0.9 forever.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Unit_Desc_1003`

**원문(KO)**

```
장시간의 현장 브리핑 후 광범위 타격을 가하며 클리버들을 쥐어짜냅니다. 부하의 노동력을 극한으로 뽑아내기에 경영진의 신임이 두텁습니다.
```

**A. grok-4.3** — 자동검증: OK

```
After a long field briefing, it unleashes wide-area strikes while squeezing every drop of labor from Cleavers. Upper management loves it for maxing out subordinate productivity.
```

**B. grok-4.6@low** — 자동검증: OK

```
After a very long on-site briefing, unleashes a wide-area strike and wrings every last drop out of the Cleavers. Management loves how it maxes out subordinate labor.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Unit_Desc_1004`

**원문(KO)**

```
수리검과 얼음 송곳을 사용합니다. 전장에서도 존재감이 희미해 가끔 아군 급여 목록에서 누락되는 버그가 있습니다.
```

**A. grok-4.3** — 자동검증: OK

```
Uses shurikens and ice spikes. Its battlefield presence is so faint it occasionally gets omitted from the friendly payroll list.
```

**B. grok-4.6@low** — 자동검증: OK

```
Uses shuriken and ice spikes. Presence is so faint even on the battlefield that it sometimes bugs out of the allied payroll list.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Unit_Desc_1005`

**원문(KO)**

```
가까운 적에게 방패를 던져 타격합니다. 본체의 안전보다 방패의 분실 여부에 더 민감해하며, 분실 시 사유서 작성을 극도로 꺼립니다.
```

**A. grok-4.3** — 자동검증: OK

```
Chucks its shield at nearby enemies. More worried about losing the shield than its own safety, and filing a loss report is its worst nightmare.
```

**B. grok-4.6@low** — 자동검증: OK

```
Throws a shield at nearby enemies. Cares more about losing the shield than the chassis, and absolutely hates writing incident reports if it goes missing.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Unit_Desc_1006`

**원문(KO)**

```
타협 없는 기술을 통해 배송 경로상의 모든 유기체적 장애물을 즉각 '처리'합니다. 가끔 멍하니 우주 밖을 응시하는 '철학적 버그'가 발생할 수 있습니다.
```

**A. grok-4.3** — 자동검증: OK

```
Handles any organic obstacles on delivery routes with zero-compromise efficiency. Occasionally glitches out staring blankly into space in a philosophical haze.
```

**B. grok-4.6@low** — 자동검증: OK

```
With zero-compromise technique, instantly 'handles' every organic obstacle on the delivery route. May occasionally stare into space due to a 'philosophical bug.'
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Unit_Desc_1007`

**원문(KO)**

```
전장에서 발생하는 오염물을 빛의 속도로 흡입하여 현장을 청결하게 유지합니다. 결벽증 프로토콜이 과하게 작동할 경우, 아직 숨이 붙어 있는 적군(혹은 아군)을 수거하려 들 수 있으니 주의하십시오.
```

**A. grok-4.3** — 자동검증: OK

```
Vacuums up battlefield mess at light speed to keep the area spotless. If its cleanliness protocol goes haywire, it might try to collect still-breathing enemies (or allies).
```

**B. grok-4.6@low** — 자동검증: OK

```
Sucks up battlefield gunk at light speed to keep the site spotless. If the cleanliness protocol overclocks, it may try to collect still-breathing enemies (or allies). Watch out.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Unit_Desc_1008`

**원문(KO)**

```
자원 채굴 및 전투 전환 기능을 탑재한 다목적 유닛입니다. 현재까지 드릴 방향은 아래를 향하고 있으나, 연구팀은 이것이 최선인지 검토 중입니다.
```

**A. grok-4.3** — 자동검증: OK

```
A versatile unit that switches between mining resources and combat. Its drill still points downward; research is still debating if that's optimal.
```

**B. grok-4.6@low** — 자동검증: OK

```
A multi-purpose unit with resource mining and combat-switch functions. So far the drill only points down, but R&D is still debating if that's optimal.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

#### `Local_Unit_Desc_1009`

**원문(KO)**

```
광역 디버프 살포 유닛입니다. 연구소 내부 시연 도중 연구원 3명이 자신이 누구인지 잊어버렸습니다. 둘은 돌아왔습니다. 하나는 아직 자기가 시크리시오라고 생각하고 있습니다.
```

**A. grok-4.3** — 자동검증: OK

```
An area debuff spreader. During an internal lab demo, three researchers forgot who they were. Two recovered. One still thinks it's Secrecio.
```

**B. grok-4.6@low** — 자동검증: OK

```
An area-debuff spray unit. During an in-lab demo, three researchers forgot who they were. Two came back. One still thinks they're Secricio.
```

**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**

---

## 참고 — 반복 실행 간 번역이 달라진 항목

같은 모델·같은 원문인데 실행마다 결과가 달랐던 항목입니다. 번역 일관성 참고용이며, 위 표에는 첫 실행 결과를 실었습니다.

| Key | 모델 | 변형 |
|---|---|---|
| `local_dialogue_1011` | grok-4.6@low | [Location Status: Gacha Galaxy]\nCoordinates are way outside the 'Safe & Compliant' zone. |
| `local_dialogue_1012` | grok-4.3 | What the heck is going on?\nAll systems are throwing up warnings. |
| `local_dialogue_1021` | grok-4.3 | Due to your unacceptable 'Protocol 7-Beta Compliance Failure', this entire area is now considered a 'Hostile Recovery Zone'. / Due to your unacceptable 'Protocol 7-Beta Compliance Failure', this entire zone is now considered a 'Hostile Recovery Zone'. |
| `local_dialogue_1021` | grok-4.6@low | Because of your unforgivable 'Protocol 7-Beta compliance failure,' this entire sector is now treated as a 'Hostile Recovery Zone.' |
| `local_dialogue_1022` | grok-4.3 | Find the boxes, 404.\nReclaim the company's assets. |
| `local_dialogue_1022` | grok-4.6@low | Find the boxes, 404.\nRecover company assets. |
| `local_dialogue_2011` | grok-4.3 | You. You chewed through the main cable during warp.\nYou're the culprit who ruined my delivery schedule. / You. You chewed through the main cable during warp.\nYou're the one who ruined my delivery schedule. |
| `local_dialogue_2011` | grok-4.6@low | You. You chewed through the main cable during warp.\nYou're the one who wrecked my delivery schedule. |
| `local_dialogue_2012` | grok-4.3 | Get back in the box right now.\nI have no intention of making a 'hazard during transport' my battle partner. / Get back in the box right now.\nI have no intention of making a 'hazard in transit' my combat partner. |
| `local_dialogue_2012` | grok-4.6@low | Get back in the box. Now.\nI am not making a 'hazard in transit' my combat partner. |
| `local_dialogue_2021` | grok-4.3 | Meow!\n(Translation: Wow, the air is great! Now, shall I slice something up?) / Meow!\n(Translation: Wow, the air's great! Time to slice some stuff up?) |
| `local_dialogue_2021` | grok-4.6@low | Meow!\n(Translation: Wow, nice air! Time to slice something up?) |
| `local_dialogue_2031` | grok-4.3 | (Sigh) Looks like a defective unit after all.\nSo this is the Schrödinger System? / (Sigh) Looks like a defective unit.\nIs this the Schrödinger system? |
| `local_dialogue_3021` | grok-4.3 | (Sigh) Free support isn't happening. It's out of my authority.\nBut there is one option available. / (Sigh) Free support isn't happening. It's outside my authority.\nThere's one option available though. |
| `local_dialogue_3021` | grok-4.6@low | (Sigh) Free support is a no. That's above my pay grade.\nThere is one option, though. / (Sigh) Free support? Not happening. Above my pay grade.\nThere is one option, though. |
| `local_dialogue_3022` | grok-4.3 | I'll approve an emergency unit drop.\nThe 1.5 million mineral activation fee will be deducted from your next paycheck. / I'll approve the emergency unit drop.\nThe 1.5 million mineral activation fee will be deducted from your next paycheck. |
| `local_dialogue_3031` | grok-4.3 | 1.5 million minerals?\nMy salary can't cover that! |
| `local_dialogue_3041` | grok-4.3 | 404, take your complaints to HR. |
| `local_speech_bubble_intro_02` | grok-4.3 | Current location is... |
| `local_speech_bubble_intro_03` | grok-4.3 | 'Company Not Liable Zone' / 'The company's not-responsible zone' |
| `local_speech_bubble_intro_03` | grok-4.6@low | 'A zone the company is not liable for' |
| `local_speech_bubble_intro_05` | grok-4.3 | Gotta find the big boss's box...! |
| `local_speech_bubble_intro_05` | grok-4.6@low | I HAVE to find the Big Boss's box...! |
| `local_speech_bubble_intro_07` | grok-4.3 | Aliens are swarming from all sides! |
| `local_speech_bubble_intro_07` | grok-4.6@low | Aliens pouring in from everywhere! |
| `local_speech_bubble_intro_09` | grok-4.3 | Is that a Churu box? Gotta grab it! / Is that the Churu box? Gotta grab it! |
| `local_speech_bubble_intro_11` | grok-4.3 | Fail and you'll get demoted to 'can opener'! / If I don't find it, I'll get demoted to 'can opener'! |
| `local_speech_bubble_intro_11` | grok-4.6@low | Fail and you're demoted to 'can opener'! |
| `local_speech_bubble_intro_12` | grok-4.3 | This box is definitely 'legendary'! |
| `local_speech_bubble_intro_12` | grok-4.6@low | This box is definitely Legendary! / This box is definitely a 'Legendary'! |
| `local_speech_bubble_intro_13` | grok-4.3 | Reinforcements have arrived! |
| `local_speech_bubble_intro_13` | grok-4.6@low | Backup units have arrived! / Reinforcement units incoming! |
| `local_speech_bubble_intro_14` | grok-4.3 | You called for just these guys? |
| `local_speech_bubble_intro_14` | grok-4.6@low | You called me\nfor THIS? / You called me\nfor just these? |
| `local_speech_bubble_intro_15` | grok-4.3 | Target spotted, target spotted. |
| `local_tutorial_2_01` | grok-4.6@low | Scanning new planet coordinates. |
| `local_tutorial_2_02` | grok-4.3 | Gather <color=#0674AC>minerals</color> to strengthen your squad.\nYou get stronger, company revenue goes up. Win-win! |
| `local_tutorial_2_04` | grok-4.3 | Summon <color=#0674AC>combat units 3 times</color>.\nCosts are on you. |
| `local_tutorial_2_04` | grok-4.6@low | <color=#0674AC>Summon combat units 3 times</color>.\nCosts are on you. / <color=#0674AC>Summon combat units 3 times</color>.\nYou're paying for it. |
| `local_tutorial_2_05` | grok-4.6@low | <color=#0674AC>Merge</color> identical units to raise their rank.\nIt's an innovative way to run one unit on two salaries. / <color=#0674AC>Merge</color> identical units to raise their rank.\nTwo salaries, one worker. Innovative, right? |
