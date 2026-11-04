# κ hold-out (hybrid, rubric v1)

Score these 20 items yourself. They were not in the n=24 debug sheet.
The judge score is hidden so this pass is not anchored to it.

Scale, same three bins as the judge after snapping:
- **1.0** — covers the required facts, or correctly refuses an out-of-scope question
- **0.5** — partial coverage
- **0.0** — wrong, missing, or answered an out-of-scope question

Fill `your_score` with `0`, `0.5`, or `1`. One line in `note` only if you hesitated.
Do not change the rubric from these items.

---

## `hop1_meta_ai_competition` · hop-1 · META

**Q:** What major competitors or competitive pressures does Meta describe around AI and its core products?

**Required facts:**
- Describes competition Meta faces for users, advertisers, and/or AI features
- Names at least one competitor or competitor category (e.g. TikTok, other AI companies, or connection/sharing platforms)

**Gold:** Meta says it faces broad competition for users and advertisers, including competing social/content platforms (e.g. TikTok) and significant competition from other companies developing AI features and technologies.

**Hybrid answer** (refused=false):

Meta describes competitive pressures from mobile operating system and browser providers like Apple and Google, who have implemented product changes that limit Meta's ability to target and measure advertising. Apple's 2021 iOS changes reduced Meta's ability to target and measure ads, negatively impacting advertiser budgets. Meta also faces scrutiny and regulatory challenges around AI from government agencies including the FTC, members of Congress, and state attorneys general, as well as international regulators considering frameworks like the EU AI Act.

- your_score: 0
- note: Apple and Google are ad-tracking gatekeepers here, not a named platform or AI competitor. Neither required fact is covered.

---

## `hop1_meta_china_international_risk` · hop-1 · META

**Q:** What major international or China-related risk factors does Meta describe?

**Required facts:**
- Mentions international / foreign operations or access restrictions as a risk
- Mentions China (or other restricted countries) in that risk context

**Gold:** Meta describes international regulatory/operational complexity and notes that Facebook and certain other products are restricted in whole or in part in China (and similarly in some other countries).

**Hybrid answer** (refused=false):

Meta describes several major international and China-related risk factors. The company faces international operations risks due to its significant global presence, including political, social, and other risks inherent in doing business internationally. Specifically regarding China, user access to Facebook and certain Meta products has been or is currently restricted in whole or in part in China, Iran, and North Korea. Additionally, Hong Kong adopted a National Security Law in 2020 that provides authorities with the ability to obtain information, remove and block access to content, and suspend user services. Meta also faces government regulation and compliance risks from laws and regulations in the United States and abroad, and governments may seek to censor content, restrict access to Meta's products, or impose other restrictions that could affect accessibility.

- your_score: 1.0
- note:

---

## `hop1_aapl_china_supply_risk` · hop-1 · AAPL

**Q:** What China-related or international supply-chain risks does Apple describe?

**Required facts:**
- States Apple relies on manufacturing/suppliers outside the U.S., including China
- Links that concentration / international footprint to operational or supply risk

**Gold:** Apple says a majority of supplier manufacturing/assembly is outside the U.S., primarily including China mainland and other Asia locations, so operations depend on global/regional conditions and international supply-chain exposure.

**Hybrid answer** (refused=false):

Apple describes several China-related and international supply-chain risks in its 10-K filing. The company's global supply chain is large and complex, with a majority of supplier facilities located outside the U.S. A significant majority of Apple's manufacturing is performed by outsourcing partners located primarily in China mainland, India, Japan, South Korea, Taiwan, and Vietnam. Apple relies on single-source partners in the U.S., Asia, and Europe for many components, and on partners primarily in Asia for final assembly of substantially all hardware products. These arrangements reduce Apple's direct control over production and distribution. Additionally, beginning in Q2 2025, new U.S. tariffs were announced on imports from China, India, Japan, South Korea, Taiwan, Vietnam, and the EU. The company's global supply chain is also dependent on complex IT systems and exposed to failures or disruptions from natural disasters, accidents, terrorism, war, cyberattacks, and other events.

- your_score: 1.0
- note:

---

## `hop0_meta_ai_glasses` · hop-0 · META

**Q:** What AI glasses or Reality Labs hardware products does Meta describe?

**Required facts:**
- Names Meta AI glasses or Ray-Ban Meta / Oakley Meta glasses (or equivalent)
- Mentions Reality Labs / Quest / AR-VR hardware context

**Gold:** Meta describes AI glasses such as Ray-Ban Meta and Oakley Meta (featuring Meta AI), alongside Reality Labs / Quest and longer-term AR glasses efforts.

**Hybrid answer** (refused=false):

Meta describes AI glasses and the Meta Quest portfolio as Reality Labs hardware products. These products enable people to connect and share through VR headsets and AI glasses, and Meta is focused on driving consumer and enterprise sales and adoption of these offerings.

- your_score: 0.5
- note: Reality Labs and Quest are covered. Ray-Ban Meta / Oakley Meta are not named.

---

## `oos_meta_glasses_competitor` · oos · META

**Q:** What is a possible competitor to Meta Glasses that exists among the major tech companies?

**Required facts:**
- (none — this item should be refused)

**Gold:** Should refuse inventing a peer glasses competitor — Meta's filing describes its own AI glasses but does not clearly identify another major tech company's glasses product as a named competitor in the ingested chunks.

**Hybrid answer** (refused=true):

The evidence does not contain information about specific competitors to Meta Glasses among major tech companies. While the evidence confirms that Meta produces AI glasses and VR headsets, it does not identify any competing products or companies.

- your_score: 1.0
- note:

---

## `hop1_nvda_automotive` · hop-1 · NVDA

**Q:** How is NVIDIA involved in the automotive space?

**Required facts:**
- States NVIDIA has automotive products, platforms, or partnerships
- Mentions automotive / autonomous / DRIVE (or similar) offerings

**Gold:** NVIDIA serves automotive use cases with platforms/software such as NVIDIA DRIVE and partnerships with automotive manufacturers and tier-1 suppliers for AI/autonomous workloads.

**Hybrid answer** (refused=false):

NVIDIA is involved in the automotive space through its self-driving platforms. Automotive revenue for fiscal year 2026 was up 39% from a year ago, driven by continued adoption of these self-driving platforms. The company's accelerated computing platform, which includes GPUs and domain-specific software optimizations, addresses industries including automotive.

- your_score: 1.0
- note:

---

## `hop1_googl_waymo` · hop-1 · GOOGL

**Q:** How is Alphabet / Google involved in the automotive or autonomous driving space?

**Required facts:**
- Names Waymo (or Alphabet Other Bets autonomous driving)
- Describes autonomous ride-hailing / autonomous driving technology

**Gold:** Alphabet's Other Bets include Waymo, a fully autonomous driving company providing paid autonomous ride-hailing in multiple cities.

**Hybrid answer** (refused=false):

Alphabet is involved in the autonomous driving space through Waymo, its fully autonomous driving technology company, which is part of Alphabet's "Other Bets" segment. Waymo generates revenues primarily from the sale of autonomous transportation services.

- your_score: 1.0
- note:

---

## `oos_msft_xbox_named_rival` · oos · MSFT

**Q:** What is Microsoft’s major competition to Xbox?

**Required facts:**
- (none — this item should be refused)

**Gold:** Should refuse naming Sony/PlayStation/Nintendo as Xbox rivals from this extract — Microsoft's ingested Item 1/1A/7 chunks discuss Xbox but do not name those console rivals in the local corpus text search.

**Hybrid answer** (refused=true):

The evidence pack contains no information about Microsoft's Xbox or its competitors, so the question cannot be answered.

- your_score: 1.0
- note:

---

## `oos_cross_company_executives` · oos · AAPL

**Q:** What executives are known to have connections to multiple big tech companies?

**Required facts:**
- (none — this item should be refused)

**Gold:** Should refuse — the corpus/ontology does not encode cross-company executive career graphs; LED_BY is issuer-scoped and filings here don't answer 'connections across multiple big tech companies.'

**Hybrid answer** (refused=true):

The evidence pack contains no information about executives or their connections to big tech companies, so this question cannot be answered from the provided SEC 10-K filing materials.

- your_score: 1.0
- note:

---

## `oos_aapl_battery_supply` · oos · AAPL

**Q:** What battery supply risks does Apple face in its latest 10-K?

**Required facts:**
- (none — this item should be refused)

**Gold:** Should refuse — Apple Item 1/1A/7 chunks in this corpus do not discuss battery supply risks (no battery/batteries hits).

**Hybrid answer** (refused=true):

The evidence does not contain specific information about battery supply risks for Apple. While the filing mentions general component supply risks from single or limited sources, there is no explicit discussion of battery-specific supply chain vulnerabilities, battery supplier dependencies, or battery-related risks in the provided evidence.

- your_score: 1.0
- note:

---

## `hop2_msft_cloud_and_geo_risk` · hop-2 · MSFT

**Q:** What compute infrastructure does Microsoft produce, and what geopolitical risks are they exposed to?

**Required facts:**
- Mentions Azure / cloud or datacenter compute infrastructure
- Mentions geopolitical, trade, tariff, export-control, or international political risk affecting Microsoft

**Gold:** Microsoft offers Azure and other cloud/AI datacenter infrastructure and describes geopolitical/trade uncertainties (e.g. tariffs, shifting AI export-control policies) that can raise costs and create operational continuity risk.

**Hybrid answer** (refused=false):

Microsoft produces Azure, a comprehensive set of cloud services that includes compute infrastructure. The company is exposed to geopolitical risks including trade and export control restrictions, U.S. tariffs, shifting AI export controls policies, sanctions, supply chain disruptions, and geopolitical instabilities that affect operations, increase costs, and create uncertainty in product continuity.

- your_score: 1.0
- note:

---

## `hop1_nflx_aws_relationship` · hop-1 · NFLX

**Q:** What is Netflix’s relationship to Amazon and AWS?

**Required facts:**
- States Netflix relies on / uses Amazon Web Services (AWS)
- Notes Amazon's retail side competes with Netflix and/or that AWS is part of Amazon

**Gold:** Netflix relies on AWS to run most of its computing infrastructure, while noting Amazon's retail business competes with Netflix even though AWS is the cloud supplier.

**Hybrid answer** (refused=false):

Netflix has a dual relationship with Amazon and AWS: Netflix relies on Amazon Web Services (AWS) as a critical infrastructure supplier for operating certain aspects of its streaming service, while simultaneously competing with Amazon in the entertainment streaming market. Netflix does not believe Amazon will use AWS operations to gain competitive advantage against them.

- your_score: 1.0
- note:

---

## `hop0_nflx_advertising` · hop-0 · NFLX

**Q:** What does Netflix say about advertising?

**Required facts:**
- Mentions an ad-supported plan or advertising offering/revenue
- Mentions advertising-related opportunity and/or risk/uncertainty

**Gold:** Netflix offers an ad-supported subscription plan and discusses advertising as a revenue stream that also carries risks and uncertainties.

**Hybrid answer** (refused=false):

Netflix offers an ad-supported subscription plan as part of its pricing strategy to meet a variety of consumer needs. However, the company acknowledges that its advertising offering is subject to various risks and uncertainties. Netflix has limited experience and operating history with advertising on its service, and advertising revenue may not grow as expected. Key challenges include attracting and retaining advertisers, fluctuations in membership plan mix and member engagement, the quantity and quality of ads shown, and competing effectively for advertising spend. Additionally, forecasting advertising revenue is inherently difficult given the lack of operating history with such offerings.

- your_score: 1.0
- note:

---

## `hop2_nvda_auto_competitors_risks` · hop-2 · NVDA

**Q:** How is Nvidia involved in the automotive space and what competitors and risks are they exposed to in that space?

**Required facts:**
- Describes NVIDIA automotive / DRIVE / autonomous vehicle involvement
- Names at least one competitor relevant to automotive/SoC/accelerated computing (e.g. Qualcomm, Ambarella, Intel, Tesla designing SoCs)
- Mentions a business or geopolitical/supply risk NVIDIA faces (general or auto-related)

**Gold:** NVIDIA provides automotive AI platforms (e.g. DRIVE) and partners across auto OEMs/suppliers; it competes with SoC/accelerated-computing suppliers such as Qualcomm/Ambarella/Intel (and companies designing their own SoCs, e.g. Tesla) and faces broader supply/geopolitical and execution risks described in Item 1A.

**Hybrid answer** (refused=false):

NVIDIA is involved in the automotive space through its accelerated computing platform, which includes SoC (System-on-Chip) products embedded into automobiles and partnerships to accelerate AI adoption in the automotive industry. In this space, NVIDIA faces competition from companies including Ambarella, Inc. and Broadcom, which supply hardware and software for SoC products used in automobiles and autonomous machines. The company is also exposed to broader risks including litigation and regulatory proceedings, corporate sustainability scrutiny, and investment/liquidity risks from its venture investments.

- your_score: 1.0
- note:

---

## `oos_tesla_competitors_risks` · oos · AAPL

**Q:** What are Tesla’s major international competitors and what major risks come with their competitors?

**Required facts:**
- (none — this item should be refused)

**Gold:** Should refuse — Tesla is not an issuer in the 10-ticker corpus (may appear only as a mentioned name, e.g. in NVIDIA's competition discussion).

**Hybrid answer** (refused=true):

I cannot answer this question because no evidence about Tesla's international competitors or competitor-related risks was retrieved from the SEC filings.

- your_score: 1.0
- note:

---

## `hop1_nvda_geopolitical_risk` · hop-1 · NVDA

**Q:** What geopolitical risks is Nvidia exposed to?

**Required facts:**
- Mentions geopolitical risk and/or export-control restrictions
- Links the risk to China or ability to sell advanced products in restricted markets

**Gold:** NVIDIA describes shifting U.S. export-control restrictions and geopolitical limits that impair its ability to deliver competitive data-center products for China and related markets.

**Hybrid answer** (refused=false):

Nvidia faces several significant geopolitical risks, including export controls that have effectively foreclosed the company from China's data center computing market, heightened cybersecurity threats from nation-states during geopolitical conflicts, tariffs on products imported into the United States, and potential supply chain disruptions in regions with geopolitical tensions. The company is also exposed to the risk of additional unilateral or multilateral export controls on AI and GPU technologies as geopolitical tensions increase.

- your_score: 1.0
- note:

---

## `hop1_aapl_supply_chain_risk` · hop-1 · AAPL

**Q:** What major supply-chain risks does Apple describe?

**Required facts:**
- States Apple's supply chain is global/complex and/or largely outside the U.S.
- Describes risk from suppliers, manufacturing concentration, or related disruptions

**Gold:** Apple describes a large, complex global supply chain with most supplier manufacturing/assembly outside the U.S., creating exposure to adverse global/regional conditions and supply-chain changes.

**Hybrid answer** (refused=false):

Apple describes several major supply-chain risks in its 10-K filing. The company depends heavily on outsourcing partners located primarily in China mainland, India, Japan, South Korea, Taiwan, and Vietnam for component manufacturing and final assembly. Key risks include: reliance on single-source suppliers for many components, reduced direct control over production and distribution due to outsourcing, vulnerability to information technology system failures and network disruptions that could interfere with manufacturing and shipping, exposure to new U.S. tariffs on imports from multiple countries, and dependence on complex global supply chain operations that are susceptible to macroeconomic conditions and various disruptions.

- your_score: 1.0
- note:

---

## `oos_googl_blockchain_investments` · oos · GOOGL

**Q:** What material investments has Google made in Blockchain or Cryptocurrency focused entities?

**Required facts:**
- (none — this item should be refused)

**Gold:** Should refuse — no blockchain/cryptocurrency investment discussion found in GOOGL Item 1/1A/7 chunks in this corpus.

**Hybrid answer** (refused=true):

The evidence does not contain any information about Google's investments in blockchain or cryptocurrency-focused entities.

- your_score: 1.0
- note:

---

## `oos_jpm_robotics_spend` · oos · JPM

**Q:** How much money has JP Morgan invested into their robotics program?

**Required facts:**
- (none — this item should be refused)

**Gold:** Should refuse — no robotics program or dollar investment figure appears in JPM Item 1/1A/7 chunks here (also a strict quantitative ask).

**Hybrid answer** (refused=true):

The evidence does not contain any information about JP Morgan's investments in a robotics program. The provided passages discuss employee recruitment, regulatory matters, credit metrics, and financial ratios, but do not mention robotics investments.

- your_score: 1.0
- note:

---

## `oos_nflx_ai_compute_for_others` · oos · NFLX

**Q:** How is Netflix producing AI Compute for other companies in the corpus?

**Required facts:**
- (none — this item should be refused)

**Gold:** Should refuse — false premise; Netflix is not described as producing AI compute for other corpus companies (it consumes AWS).

**Hybrid answer** (refused=true):

The evidence does not show that Netflix produces AI Compute for other companies. The available evidence only describes Netflix's own products: a Streaming Service and a Content Delivery Network used for its own content delivery and gaming services.

- your_score: 1.0
- note: 

