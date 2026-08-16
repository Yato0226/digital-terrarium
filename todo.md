# Terrarium Feature Roadmap: Stage 10+ Master Blueprint

## Phase 1: Streamline Discord into a Milestone News Hub
*Goal: Stop every-minute embed spam and turn your Discord channels into a clean, exciting newspaper of major colony events.*

### Step 6: The Milestone Announcement System
- [x] Cease sending embeds every 60 seconds.
- [x] Restrict automated Discord posts to high-impact milestones only:
  - [x] **Season Change & Era Chronicle**: Posted every 100 ticks with the Lorekeeper's era title and paragraph.
  - [x] **Fallen Heroes & Eulogies**: Posted immediately when a colonist dies with their tombstone inscription and cause of death.
  - [x] **Annual Patch Notes**: Posted every 400 ticks with the Architect's balance tuning, synthesized blueprints, and prophecies.
  - [x] **Breaking Crisis Alerts**: Instant notifications when an Autumn Scavenger Raid strikes, a Wildfire reaches the camp, or Total Extinction occurs.
  - [x] **Adoption Milestones**: Direct DMs to users when their adopted ward gives birth, achieves a goal, or suffers a mental break.

---

## Phase 2: Living Memory, Biographies & Generational Sagas
*Goal: Turn the event log into deep historical memory that persists across generations.*

### Step 7: The Pawn Biography Engine (`!bio <name>`)
- [x] Create a biography command where Gemma parses a colonist's raw event history from the log file and synthesizes it on demand into a 3-sentence heroic saga or obituary.
- [x] Viewers can inspect living elders or read the full life stories of ancestors buried in the graveyard.

### Step 8: Generational Handoffs & Dynasties
- [x] When Generation 1 dies out, Generation 2 and 3 take over the colony.
- [x] Ancestral graves, inherited heirlooms, and family deeds remain permanently referenced in future prompt contexts so ancestors are never forgotten.

### Step 9: The Monolith as an Oracle & Rune Archive
- [ ] Significant colony achievements get carved into the Ancestral Monolith as permanent historical runes.
- [ ] Colonists can pray at the monolith to receive prophetic visions, divine inspiration, or weather warnings.

### Step 10: Ancient Pre-History (The Lost Tribe)
- [ ] Turn the Ruins tile into the named remnants of an ancient civilization (*The Sunken Tribe*).
- [ ] Scouts exploring the ruins discover fragments of forgotten history, ancient tool blueprints, and carved warnings.

---

## Phase 3: Social Dynamics, Factions & Dynamic Roles
*Goal: Transform flat relationship numbers into living social drama and emergent colony governance.*

### Step 11: Qualitative Relational Badges
- [ ] Attach meaningful badges based on actual deeds: *Lifesaver*, *Betrayer*, *Indebted*, *Mentor*, *Widow*.
- [ ] The AI Director uses these badges to weave deep, specific social drama and dialogue into tick narratives.

### Step 12: Multigenerational Blood Feuds
- [ ] If two colonists become bitter rivals, their children inherit the feud at birth.
- [ ] New generations must choose between making peace through courtship and sharing food, or escalating the feud into camp brawls during elections.

### Step 13: Free-Form Dynamic Roles with Keyword Bucketing
- [ ] Allow the LLM to organically invent custom job titles based on pawn deeds (*"Fang-Breaker"*, *"Keeper of the Hearth"*).
- [ ] The engine uses keyword matching to safely grant subtle passive perks (martial words boost defense, nurturing words boost food sharing, spiritual words speed up grief recovery).

### Step 14: Annual Camp Council & Colony Mandates
- [ ] Every year cycle, the LLM reviews colony history, names a recognized leader, and issues a 1-sentence **Colony Mandate** (e.g. *"Tame the beasts of the wood"* or *"Fortify before raiders return"*), giving all colonists a unified narrative focus.

---

## Phase 4: Living Ecosystem, Cataclysms & Exploration
*Goal: Make the wilderness dynamic, reactive, and dangerous.*

### Step 15: Trophic Cascades (Food Chain Ecology)
- [ ] Over-hunting wolves removes predator pressure, causing deer and rabbits to overpopulate, eat wild forage, and damage farm plots.
- [ ] Clear-cutting forests removes windbreaks, making winter cold harsher and increasing the risk of spring river floods.

### Step 16: Persistent Named Legendary Beasts
- [ ] If a predator injures multiple colonists and escapes, it gains a permanent name and reputation (*The Grey Terror*, *Old Scar-Face*), triggering colony-wide revenge hunts.

### Step 17: Fog of War & Off-Grid Expeditions
- [ ] Shroud the outer rim of the 5×5 map in mist, requiring Scouts to actively explore and map the perimeter.
- [ ] Allow pairs of colonists to pack rations and leave the map for 15–20 ticks on background expeditions, returning with rare loot, exotic seeds, unique pets, or battle scars.

### Step 18: Multi-Tick Seasonal Cataclysms
- [ ] Introduce multi-tick environmental trials such as *The Long Winter* (150 ticks of intense freeze and double fuel drain) or *The Great Drought* (halting river forage and dramatically spiking wildfire danger).

---

## Phase 5: Emergent Mythology, Religion & Full Interconnection
*Goal: Connect all systems into a self-sustaining, emergent civilization saga.*

### Step 19: Dynamic Colony Identity & Taboos
- [ ] The colony earns an evolving community name based on what it survives (*The Hearthfolk*, *The Ashen Kin*).
- [ ] Emergent cultural taboos develop naturally (e.g. fearing the Ruins after casualties, causing low-bravery pawns to avoid those tiles).

### Step 20: The Voice in the Sky & Camp Shrines
- [ ] Colonists who receive frequent God whispers (`!say`) become spiritual leaders or "Prophets."
- [ ] The colony builds small shrines and leaves food offerings at camp to appease the Creator.

### Step 21: Physical Folklore & Herbal Medicine
- [ ] Artisans paint cave murals or carve wooden totems celebrating major historical events, giving future generations positive moodlets.
- [ ] Foragers gather medicinal herbs from meadows to brew salves and nurse sick colonists back to health.

### Step 22: The Domino Effect (Total Interconnection)
- [ ] Close the full causal loop:
  - [ ] *Hazard strikes → Wood stock burns → Campfire dies → Morale collapses → Berserk break → Ancestor falls → Grave marked → Legend carved into Monolith → New tradition forged.*

---

## Phase 6: The Live Isometric Visual Engine & Discord Activity
*Goal: Turn the simulation into a real-time, 60 FPS floating diorama that members can watch directly inside Discord voice channels.*

### Step 1: Lightweight State Broadcast
- [ ] Set up a minimal WebSocket feed in your backend that broadcasts a clean JSON snapshot of the world whenever a tick completes.
- [ ] Keep it ultra-lightweight so it consumes barely any extra RAM on your 2 GB container while running quietly in the background.

### Step 2: The Floating Isometric Diorama Client
- [ ] Build a lightweight browser view that renders the 5×5 grid as an isometric floating island cube with cutaway dirt and stone layers underneath.
- [ ] Use **Client-Side Interpolation** so the 60-second tick feels like a live game:
  - [ ] Seconds 0 to 4: Pawns walk diagonally across the diamond grid to their destination.
  - [ ] Seconds 4 to 12: Speech and thought bubbles float and fade.
  - [ ] Seconds 12 to 55: Continuous looping animations (swinging axes at trees, foraging bushes, sitting by the fire, sleeping).
  - [ ] Continuous: Atmospheric particle loops (river water flowing, campfire smoke rising, wind swaying trees).

### Step 3: Comic Speech & Thought Bubbles
- [ ] **Outward Speech (`quote`)**: Comic-style dialogue bubbles pop up above character sprites for nearby colonists to "hear."
- [ ] **Inner Thoughts (`inner_monologue`)**: Soft, cloudy dream bubbles float above pawns, revealing their secret schemes, fears, or romantic feelings to the viewer.
- [ ] **Status Emotes**: Floating icons over heads for chopping, heart emotes for courtship, red anger marks during fights, and sleeping Zzz's.

### Step 4: Full Interactive On-Screen Dashboard (HUD)
Move all the heavy information out of Discord and onto the web screen:
- [ ] **Top Bar**: Live Season, Weather, Day/Night clock, Campfire %, Shelter %, and Wood/Food/Stone/Fiber resource stockpiles.
- [ ] **Bottom Narrative Ticker**: Real-time scrolling feed of the AI Director's 2-sentence world summary and recent event logs.
- [ ] **Click-to-Inspect Pawn Dossier**: Clicking any pawn highlights a glowing ring under their feet and opens a side card showing their health, energy, equipped tools, rucksack contents, active goals, and family lineage.
- [ ] **Lore Archives**: Dedicated tabs in the web client for browsing the Graveyard epitaphs, Monolith inscriptions, and Architect patch notes.

### Step 5: Cloudflare Named Tunnel & Discord Activity Embedding
- [ ] Set up a permanent named tunnel in your Cloudflare Zero Trust dashboard pointing to your local terrarium port.
- [ ] Install the background connector on your container so it auto-starts on boot.
- [ ] Paste your permanent HTTPS address into the Discord Developer Portal under **Activities / URL Mappings**.
- [ ] Server members can now click the **Rocket Activity icon** in any Discord voice channel to launch the live floating terrarium right inside Discord!

---

This step-by-step blueprint takes you from the core visual setup to an unforgettable, living autonomous civilization simulation!
