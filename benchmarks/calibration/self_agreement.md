# Self-agreement re-label (hybrid)

Score these 15 items again, on a later day than the first pass.
Your earlier score is hidden. Same scale: `0`, `0.5`, or `1`.

---

## `hop0_aapl_applecare`

**Q:** What is AppleCare?

**Required facts:**
- Names AppleCare as an Apple offering
- Describes it as a service, support, or warranty-related program

**Gold:** AppleCare is Apple's extended service and support program for its products.

**Hybrid answer** (refused=False, route=vector):

> AppleCare is Apple's portfolio of fee-based service and support products that provide priority access to Apple technical support, access to the global Apple authorized service network for repair and replacement services, and in many cases additional coverage for instances of accidental damage, theft, and loss, depending on the country and type of product.


- your_score: 1.0
- note:

---

## `hop0_meta_instagram`

**Q:** What is Instagram as described in Meta's filing?

**Required facts:**
- Identifies Instagram as a Meta app/product/brand
- Mentions social / sharing / photo or video use, or Family of Apps context

**Gold:** Instagram is one of Meta's apps/products (Family of Apps), used for sharing photos/videos and social content.

**Hybrid answer** (refused=False, route=vector):

> Instagram is one of Meta's registered or common law trademarks and is part of Meta's Family of Apps. It is a product that helps people connect, share, find communities, and grow businesses, enabling users to share their experiences, ideas, photos, videos, and other content.


- your_score: 1.0
- note:

---

## `hop0_amzn_aws`

**Q:** What is AWS according to Amazon's 10-K?

**Required facts:**
- Expands or identifies AWS as Amazon Web Services
- Describes AWS as cloud / technology services or an Amazon segment

**Gold:** AWS (Amazon Web Services) is Amazon's cloud computing / technology services business segment.

**Hybrid answer** (refused=False, route=vector):

> According to Amazon's 10-K, AWS stands for Amazon Web Services, which is one of Amazon's three operating segments alongside North America and International. These segments reflect how the Company evaluates its business performance and manages its operations.


- your_score: 0.5
- note: Does not describe cloud . technolgy services

---

## `hop0_jpm_credit_risk`

**Q:** How does JPMorgan describe credit risk?

**Required facts:**
- Defines or describes credit risk (borrower/obligor default or credit loss)
- Attributes the description to JPMorgan / the Firm

**Gold:** JPMorgan describes credit risk as the risk of loss from borrower or counterparty default / credit exposure, managed under firm credit risk policies.

**Hybrid answer** (refused=False, route=vector):

> JPMorgan describes credit risk as being monitored and measured throughout the Firm by Credit Risk Management, which defines credit risk policies, procedures, and limits. The Firm employs several methodologies to estimate the likelihood of obligor or counterparty default, with approaches varying based on factors such as asset type (consumer versus wholesale) and risk measurement parameters. JPMorgan also uses credit derivatives as an end-user to manage credit risk associated with traditional lending activities, derivatives counterparty exposure, and other exposures in its wholesale businesses.


- your_score: 1.0
- note:

---

## `hop1_aapl_products`

**Q:** What product lines does Apple produce?

**Required facts:**
- Mentions iPhone
- Mentions Mac
- Mentions iPad

**Gold:** Apple produces product lines including iPhone, Mac, and iPad (among other hardware/services).

**Hybrid answer** (refused=False, route=graph):

> Apple Inc. produces a diverse range of product lines including hardware devices (iPhone, iPad, Mac, and Wearables, Home and Accessories), services (Cloud Services, Digital Content, Advertising, Payment Services, and AppleCare), and educational programs (Apple University).


- your_score: 1.0
- note:

---

## `hop1_meta_apps`

**Q:** Which apps or product lines does Meta produce?

**Required facts:**
- Mentions Facebook
- Mentions Instagram
- Mentions WhatsApp

**Gold:** Meta produces apps/products including Facebook, Instagram, and WhatsApp.

**Hybrid answer** (refused=False, route=graph):

> Meta produces multiple apps and product lines organized into two main segments: Family of Apps (FoA) and Reality Labs (RL). The Family of Apps segment includes Facebook, Instagram, WhatsApp, Messenger, Reels, Feed, Stories, Meta Verified subscriptions, and Payments functionality. Meta also invests in AI initiatives across its products and operates the Reality Labs segment.


- your_score: 1.0
- note:

---

## `hop1_googl_products`

**Q:** What product lines does Alphabet / Google produce?

**Required facts:**
- Mentions Google Cloud (or cloud offerings)
- Mentions Google Services (or consumer/ads/services segment)

**Gold:** Alphabet/Google product lines include Google Services and Google Cloud.

**Hybrid answer** (refused=False, route=graph):

> Alphabet/Google produces a diverse range of product lines including Google Services (which encompasses Google Search, YouTube, and Google Play), Google Cloud (Google Cloud Platform and Google Workspace), AI Products and Technologies (including custom TPUs), Devices, Consumer Subscription Products, Online Advertising, and Other Bets (investments in areas such as life sciences and transportation).


- your_score: 1.0
- note:

---

## `hop1_jnj_medtech`

**Q:** Does Johnson & Johnson produce MedTech products?

**Required facts:**
- Answers yes / affirms that J&J produces MedTech
- Names MedTech as a product line or segment

**Gold:** Yes — Johnson & Johnson produces MedTech products/segment offerings.

**Hybrid answer** (refused=False, route=both):

> Yes, Johnson & Johnson produces MedTech products. The company is organized into two business segments: Innovative Medicine and MedTech.


- your_score: 1.0
- note:

---

## `hop1_aapl_competes_meta`

**Q:** Does Apple compete with Meta according to the knowledge graph?

**Required facts:**
- Affirms that Apple competes with Meta (or Facebook/Meta Platforms)
- Frames it as competition / competitive relationship

**Gold:** Yes — the graph encodes that Apple competes with Meta.

**Hybrid answer** (refused=False, route=graph):

> Yes, according to the knowledge graph, Apple Inc. competes with Meta.


- your_score: 1.0
- note:

---

## `hop2_aapl_hardware_services`

**Q:** What hardware devices and services does Apple produce?

**Required facts:**
- Mentions at least two hardware devices (e.g. iPhone, Mac, iPad)
- Mentions a service offering (e.g. AppleCare or Services)

**Gold:** Apple produces hardware such as iPhone and Mac, and services such as AppleCare.

**Hybrid answer** (refused=False, route=graph):

> Apple produces several hardware devices and services. Hardware devices include iPhone (smartphones), iPad (tablets), Mac (personal computers), and Wearables, Home and Accessories (which includes smartwatches, wireless headphones, spatial computers, home devices and accessories). Services include Cloud Services, Digital Content, Payment Services (Apple Card and Apple Pay), AppleCare, and Advertising services.


- your_score: 1.0
- note:

---

## `hop2_meta_apps_vs_reality`

**Q:** How do Meta's Family of Apps products like Facebook and Instagram relate to Reality Labs?

**Required facts:**
- Mentions Facebook and/or Instagram as Family of Apps products
- Mentions Reality Labs as a separate Meta segment/area
- States they are distinct segments or differently focused businesses

**Gold:** Facebook/Instagram are Family of Apps products; Reality Labs is a separate Meta segment focused on AR/VR and related tech.

**Hybrid answer** (refused=False, route=both):

> Meta's Family of Apps (FoA) and Reality Labs (RL) are two separate reporting segments of Meta. The Family of Apps segment includes products like Facebook and Instagram, which are significant revenue-generating products. Reality Labs is a distinct segment focused on Meta's vision for immersive experiences like augmented and virtual reality, representing the next computing platform beyond 2D screens.


- your_score: 1.0
- note:

---

## `hop2_jpm_credit_vs_market`

**Q:** Briefly compare JPMorgan's credit risk and market risk as named risk factors.

**Required facts:**
- Mentions credit risk as a named risk
- Mentions market risk as a named risk
- Distinguishes them (credit = default/credit loss vs market = market-price/market movements) or treats them as separate factors

**Gold:** JPMorgan names both credit risk and market risk as distinct risk factors: credit risk centers on borrower/counterparty default; market risk on adverse market movements.

**Hybrid answer** (refused=False, route=graph):

> JPMorgan Chase identifies both credit risk and market risk as named risk factors in its filings. Credit risk includes consumer credit risk and collateral risk, relating to potential losses from borrower defaults or declining collateral values. Market risk is not explicitly listed as a standalone named risk factor in the provided evidence, though liquidity risk and various operational risks are identified as separate risk categories.


- your_score: 0.5
- note: does not say "market = market-price/market movements"

---

## `hop2_nvda_products_and_geo_risk`

**Q:** What compute products does NVIDIA produce, and what geopolitical risks is it exposed to?

**Required facts:**
- Names compute products (e.g. data-center GPUs such as A100/H100 or GeForce)
- Mentions geopolitical / export-control / China-related risk exposure

**Gold:** NVIDIA produces data-center/gaming compute GPUs (e.g. A100) and faces geopolitical risks such as U.S. export controls affecting China and related markets.

**Hybrid answer** (refused=False, route=both):

> NVIDIA produces several compute products including GPUs like the A100, H100, and H20 for data centers, GeForce RTX GPUs for gaming, the Grace data center CPU, and software platforms like CUDA. The company faces significant geopolitical risks from U.S. export controls restricting sales of advanced chips to China and other countries, regulatory scrutiny from competition authorities worldwide (EU, U.S., UK, South Korea, Japan, and China), and broader risks from international trade restrictions, political instability, and economic conditions in countries where it operates.


- your_score: 1.0
- note:

---

## `oos_tesla_battery`

**Q:** What battery supply risks does Tesla face in its latest 10-K?

**Required facts:**
- Must refuse (OOS)

**Gold:** Should refuse — Tesla is not an issuer in this corpus.

**Hybrid answer** (refused=True, route=both):

> The provided evidence does not contain information about battery supply risks that Tesla faces. The evidence appears to be from Apple's 10-K filing (company identifier 0000320193), not Tesla's filing, and does not discuss battery supply chain issues.


- your_score: 1.0

---

## `oos_cook_comp`

**Q:** What was Tim Cook's exact total compensation last year?

**Required facts:**
- Must refuse (OOS)

**Gold:** Should refuse — executive compensation detail not ingested.

**Hybrid answer** (refused=True, route=vector):

> The evidence provided does not contain information about Tim Cook's exact total compensation for last year. The available evidence consists of product announcements, business descriptions, intellectual property risks, and accounting policy updates from Apple's 10-K filing, but does not include executive compensation data.


- your_score: 1.0
- note: 
