"""Seed articles, part A: Technology, Science, Business & Economy, Health, Environment.

Each entry: title, category, tags, summary, body (list of paragraphs; "## " starts a sub-heading).
"""

ARTICLES_A = [
    # ------------------------------------------------------------------ Technology
    {
        "title": "How Search Engines Decide Which Page Comes First",
        "category": "Technology",
        "tags": ["Search", "Algorithms", "Information Retrieval"],
        "summary": "Behind every results page is a pipeline that cleans text, builds an inverted index and scores documents. Here is what happens in the half-second after you press Enter.",
        "body": [
            "Typing a few words into a search box feels effortless, but the system on the other side has done most of its work long before you arrived. Crawlers collect pages, and an indexing pipeline breaks every document into tokens: lower-cased words with punctuation removed, sometimes reduced to a common stem so that 'running' and 'runs' meet at 'run'.",
            "## The inverted index",
            "Those tokens feed an inverted index, a structure that works like the index at the back of a textbook. Instead of listing the words on each page, it lists, for every word, the pages that contain it and how often. Answering a query becomes a matter of fetching a few short lists and intersecting them rather than scanning millions of documents.",
            "## Scoring relevance",
            "Classic ranking functions such as TF-IDF and BM25 then reward documents where the query terms appear often, while discounting words that appear everywhere. BM25 adds two refinements: repeated mentions have diminishing returns, and long documents are not automatically favoured. Modern engines layer click behaviour, freshness and link signals on top, but the core idea has stayed remarkably stable for decades.",
        ],
    },
    {
        "title": "Passkeys Explained: Logging In Without a Password",
        "category": "Technology",
        "tags": ["Security", "Authentication", "Privacy"],
        "summary": "Passkeys replace the password with a pair of cryptographic keys stored on your device. They resist phishing by design, but switching takes some planning.",
        "body": [
            "A passkey is a credential made of two linked keys. The private key never leaves your phone, laptop or hardware token; the website only stores the public half. When you sign in, the site sends a challenge, your device signs it after you unlock it with a fingerprint, face scan or PIN, and the site verifies the signature.",
            "Because nothing secret is typed or transmitted, there is no password for a fake login page to steal. Each passkey is also bound to the real domain of the site that created it, so a look-alike address simply cannot request it. That property alone removes the most common route into personal accounts.",
            "The practical hurdles are about recovery. If all your devices are lost, you need a synced backup through your platform's keychain or a second registered device. Security teams recommend registering at least two passkeys for important accounts and keeping a recovery code in a safe place while the ecosystem matures.",
        ],
    },
    {
        "title": "Why Your Phone Battery Ages and How to Slow It Down",
        "category": "Technology",
        "tags": ["Batteries", "Smartphones", "Consumer Tech"],
        "summary": "Lithium-ion cells lose capacity with every cycle, but heat and time spent at full charge do more damage than most people realise.",
        "body": [
            "Every lithium-ion battery slowly loses the ability to hold charge. Inside the cell, lithium ions shuttle between two electrodes, and each trip leaves a little debris behind in the form of side reactions that consume active material. After a few hundred full cycles, a typical phone battery holds noticeably less energy than it did on day one.",
            "Cycles are not the whole story. Batteries age fastest when they are hot and when they sit at very high or very low charge for long periods. Leaving a phone on a car dashboard in summer, or charging it under a pillow overnight, accelerates wear far more than an extra charge during the day.",
            "Most modern phones offer an optimised or limited charging mode that pauses at around 80 percent and finishes just before you usually unplug. Turning it on, avoiding heat, and not worrying about small top-ups are the three habits that make the biggest difference over the life of a device.",
        ],
    },
    {
        "title": "A Beginner's Guide to Large Language Models",
        "category": "Technology",
        "tags": ["Artificial Intelligence", "Machine Learning", "Language"],
        "summary": "Language models predict the next word, yet that simple objective produces systems that can summarise, translate and write code. What they are good at, and where they still stumble.",
        "body": [
            "A large language model is trained on a vast collection of text to do one thing: predict the next token, a word or fragment of a word, given everything that came before. Repeating that prediction step by step produces sentences, paragraphs and entire documents.",
            "To make good predictions across so many topics, the model has to capture grammar, facts, writing styles and patterns of reasoning. That is why the same system can draft an email, explain a chemistry concept and suggest a fix for a programming error without being built separately for each task.",
            "The same mechanism explains their weaknesses. A model can produce fluent text that sounds certain but is wrong, especially about niche or recent facts. Good practice is to treat its output as a draft: ask for sources, check numbers, and use retrieval tools that ground answers in documents you trust.",
        ],
    },
    {
        "title": "Edge Computing: Bringing the Cloud Closer to You",
        "category": "Technology",
        "tags": ["Cloud", "Networking", "Infrastructure"],
        "summary": "Self-checkout cameras, factory sensors and video calls all benefit when computation happens a few kilometres away instead of a continent away.",
        "body": [
            "For most of the last decade, the default answer to any computing problem was to send the data to a large cloud region and process it there. Edge computing flips part of that model by running workloads on small servers placed in telecom exchanges, retail stores or factories, physically close to where data is produced.",
            "The main benefit is latency. A round trip to a distant data centre can take a hundred milliseconds or more, which is too slow for a robot arm that must stop instantly or a game that needs to feel responsive. Processing locally also reduces bandwidth costs, because only summaries rather than raw video need to travel upstream.",
            "The trade-off is operational complexity. Thousands of small sites are harder to secure, update and monitor than a handful of large ones. Teams adopting edge platforms typically invest early in automated deployment and remote observability so that a server in a supermarket back room can be managed like any other cloud resource.",
        ],
    },
    {
        "title": "What Makes a Good Database Index",
        "category": "Technology",
        "tags": ["Databases", "Performance", "Software Engineering"],
        "summary": "Indexes can turn a ten-second query into a ten-millisecond one, but every index has a cost. A practical look at when to add one.",
        "body": [
            "A database index is a separate, sorted structure that lets the engine find rows without reading the whole table. Most relational databases use B-trees, which keep keys in order and allow lookups, range scans and sorting in logarithmic time.",
            "The best candidates are columns used in WHERE clauses, JOIN conditions and ORDER BY on large tables. Composite indexes help when queries filter on several columns together, but column order matters: an index on (category, published_at) supports filtering by category and sorting by date, while the reverse order does not.",
            "Indexes are not free. Every insert and update must also update each index, and they take disk space and memory. A good habit is to measure with the database's query plan tool, add indexes for the slow queries you actually run, and remove ones that the statistics show are never used.",
        ],
    },
    # ------------------------------------------------------------------ Science
    {
        "title": "How Scientists Measure the Age of the Universe",
        "category": "Science",
        "tags": ["Astronomy", "Cosmology", "Physics"],
        "summary": "Two independent methods, one using the oldest light in the sky and one using nearby exploding stars, both point to roughly 13.8 billion years, with a puzzling disagreement in the details.",
        "body": [
            "The first method reads the cosmic microwave background, faint radiation released when the universe cooled enough for atoms to form. Tiny temperature variations in that glow encode the density and composition of the early cosmos. Feeding those measurements into the standard cosmological model yields an age of about 13.8 billion years.",
            "The second method works outward from our neighbourhood. Astronomers measure distances to nearby galaxies using stars with known brightness, then use certain supernovae as markers to reach farther. Comparing distance with the speed at which galaxies recede gives the expansion rate, known as the Hubble constant.",
            "The two approaches agree on the broad picture but give slightly different expansion rates, a gap often called the Hubble tension. Whether it reflects measurement errors or new physics is one of the most active questions in cosmology, and upcoming telescope surveys are designed specifically to resolve it.",
        ],
    },
    {
        "title": "The Hidden Life of Soil Microbes",
        "category": "Science",
        "tags": ["Biology", "Ecology", "Agriculture"],
        "summary": "A teaspoon of healthy soil contains more microorganisms than there are people on Earth. They recycle nutrients, store carbon and help plants fight disease.",
        "body": [
            "Soil looks inert, but it is one of the most crowded habitats on the planet. Bacteria, fungi, protists and microscopic animals form food webs that break down dead leaves and roots, releasing nitrogen, phosphorus and other nutrients in forms plants can absorb.",
            "Many plants form partnerships with mycorrhizal fungi, whose fine threads extend the reach of roots far beyond what the plant could manage alone. In exchange for sugars, the fungi deliver water and minerals. Some studies suggest these networks can even shuttle chemical signals between neighbouring plants.",
            "Farming practices strongly shape these communities. Frequent ploughing breaks fungal networks, while cover crops, reduced tillage and compost tend to increase microbial diversity. Researchers are now testing whether managing soil biology deliberately can cut fertiliser use and lock more carbon underground.",
        ],
    },
    {
        "title": "Why Do We Dream? What Sleep Research Tells Us",
        "category": "Science",
        "tags": ["Neuroscience", "Sleep", "Psychology"],
        "summary": "Dreams may help the brain sort memories and rehearse emotional situations, but no single theory explains them all.",
        "body": [
            "Most vivid dreams occur during rapid eye movement sleep, a stage in which the brain is almost as active as when awake while most muscles are temporarily paralysed. Adults cycle through REM several times a night, with periods growing longer toward morning.",
            "One leading idea is that sleep helps consolidate memories, replaying recent experiences and linking them with older knowledge. Experiments show that people who sleep after learning a task often perform better than those who stay awake, and some report dreaming about the task itself.",
            "Another view sees dreams as a kind of emotional simulation, a safe space to rehearse threats or social conflicts. The theories are not mutually exclusive, and researchers increasingly suspect that dreaming serves several purposes at once rather than a single function.",
        ],
    },
    {
        "title": "Quantum Computers: What They Can and Cannot Do",
        "category": "Science",
        "tags": ["Quantum Computing", "Physics", "Computing"],
        "summary": "Quantum machines will not replace laptops, but for specific problems in chemistry and optimisation they could offer a dramatic advantage.",
        "body": [
            "Classical computers store information as bits that are either zero or one. Quantum computers use qubits, which can exist in superpositions of both states and become entangled with one another. Carefully designed algorithms use interference between these states to make correct answers more likely when the machine is measured.",
            "This does not make quantum computers faster at everything. Their advantage applies to particular problems: simulating molecules, factoring large numbers and some kinds of search and optimisation. For browsing the web or editing documents, a classical chip remains far better.",
            "The main obstacle today is noise. Qubits lose their delicate states quickly, so useful computations require error correction that combines many physical qubits into one reliable logical qubit. Progress is steady, but most experts expect broad practical impact to arrive gradually rather than all at once.",
        ],
    },
    {
        "title": "How Vaccines Train the Immune System",
        "category": "Science",
        "tags": ["Immunology", "Medicine", "Public Health"],
        "summary": "Whether built from weakened viruses, proteins or messenger RNA, vaccines all work by giving the immune system a safe preview of a pathogen.",
        "body": [
            "The immune system learns by example. When it meets a new pathogen, specialised cells recognise distinctive molecules called antigens and begin producing antibodies and killer cells tailored to them. That first response takes days, which is why a first infection can make us seriously ill.",
            "Vaccines provide the example without the danger. Some contain inactivated or weakened viruses, others contain purified proteins, and newer mRNA vaccines deliver instructions that let our own cells briefly produce a harmless piece of the pathogen. In every case, the immune system responds and keeps memory cells ready.",
            "If the real pathogen appears later, those memory cells react within hours instead of days. Because immunity can fade or viruses can change, some vaccines need boosters. Population-wide vaccination also protects people who cannot be vaccinated themselves by making outbreaks less likely to take hold.",
        ],
    },
    {
        "title": "The Physics of a Perfect Paper Airplane",
        "category": "Science",
        "tags": ["Physics", "Aerodynamics", "Education"],
        "summary": "Lift, drag, thrust and balance decide whether a folded sheet glides across a hall or nosedives at your feet.",
        "body": [
            "A paper airplane obeys the same four forces as an airliner. Your throw supplies thrust, drag slows the plane down, gravity pulls it toward the floor and lift from the wings pushes it upward. A long flight comes from balancing these forces rather than maximising any one of them.",
            "Balance is the most overlooked factor. The centre of gravity should sit slightly ahead of the centre of lift, which is why many good designs fold extra layers of paper into the nose. If the nose is too light, the plane pitches up, stalls and drops; too heavy, and it dives.",
            "Small adjustments to the trailing edges of the wings act like an aircraft's elevators. Bending them up slightly raises the nose and can turn a dive into a glide. Experimenting with one change at a time is a classic, inexpensive way to teach the scientific method in a classroom.",
        ],
    },
    # ------------------------------------------------------------------ Business & Economy
    {
        "title": "Inflation Explained in Five Everyday Purchases",
        "category": "Business & Economy",
        "tags": ["Inflation", "Personal Finance", "Economics"],
        "summary": "From coffee to rent, the prices you notice most are shaped by different forces. Understanding them makes economic news easier to follow.",
        "body": [
            "Inflation is the general rise in prices over time, usually measured by tracking a basket of goods and services that typical households buy. When people say inflation is three percent, they mean that basket costs about three percent more than a year earlier, not that every item rose by the same amount.",
            "Food prices often react quickly to weather, fuel costs and global commodity markets, which is why a cup of coffee can jump while other prices stay calm. Rent moves more slowly, because leases are renewed only once a year, so housing costs can keep rising long after other prices have settled.",
            "Central banks respond to persistent inflation by raising interest rates, which cools borrowing and spending. The effect works with a delay of many months, which explains why policymakers talk about data trends rather than any single monthly figure.",
        ],
    },
    {
        "title": "How Small Businesses Can Start Selling Online",
        "category": "Business & Economy",
        "tags": ["E-commerce", "Small Business", "Marketing"],
        "summary": "Opening a web shop is easier than ever, but logistics, photos and customer service decide whether it succeeds.",
        "body": [
            "Hosted store builders let a shop owner set up a catalogue, take card payments and calculate shipping in an afternoon. The technology is rarely the hard part. Choosing which products to list first, and pricing them to cover packaging and delivery, matters far more.",
            "Good product photos and honest descriptions are the online equivalent of a well-arranged shop window. Customers cannot touch the item, so measurements, materials and clear return policies reduce both hesitation and costly returns.",
            "Finally, fulfilment needs a routine. Many small sellers set fixed shipping days, keep a simple stock spreadsheet in sync with the website, and answer messages within one business day. Those habits build the reviews and repeat customers that advertising alone cannot buy.",
        ],
    },
    {
        "title": "The Rise of the Four-Day Work Week",
        "category": "Business & Economy",
        "tags": ["Work", "Productivity", "Management"],
        "summary": "Trials in several countries suggest compressed schedules can maintain output while improving wellbeing, but the model does not suit every job.",
        "body": [
            "The idea is simple: employees work four days instead of five while keeping the same pay, on the understanding that productivity holds steady. Pilot programmes run by companies and researchers have reported lower burnout, fewer sick days and easier recruitment among participants.",
            "Making it work usually requires cutting low-value activity rather than squeezing five days into four. Teams in successful trials shortened meetings, reduced internal email and set clearer priorities. Without those changes, a shorter week can simply mean longer and more stressful days.",
            "Some roles, such as hospital wards, shops and customer support lines, need coverage every day, so organisations use staggered rotas rather than closing on Fridays. The debate is less about whether the model can work and more about where and how it fits.",
        ],
    },
    {
        "title": "What Is a Supply Chain and Why Does It Break?",
        "category": "Business & Economy",
        "tags": ["Logistics", "Supply Chain", "Global Trade"],
        "summary": "A single product can depend on dozens of suppliers across several continents. When one link fails, shortages spread quickly.",
        "body": [
            "A supply chain is the network of companies, transport routes and warehouses that turns raw materials into a finished product on a shelf. Even a simple kettle may involve mined metals, plastic pellets, electronic components, assembly plants, container ships and trucks.",
            "For years many firms optimised these chains for low cost and minimal inventory, an approach known as just-in-time. It works well when everything runs smoothly but leaves little buffer for disruption, whether from a port closure, a factory fire or a sudden spike in demand.",
            "Since recent disruptions, businesses have been rebalancing. Common strategies include keeping more safety stock of critical parts, qualifying a second supplier in another region and using software that maps suppliers' own suppliers to reveal hidden dependencies.",
        ],
    },
    {
        "title": "Understanding Interest Rates and Your Mortgage",
        "category": "Business & Economy",
        "tags": ["Personal Finance", "Housing", "Interest Rates"],
        "summary": "Fixed or variable, short or long term: small differences in a mortgage rate add up to large sums over decades.",
        "body": [
            "A mortgage rate is the price of borrowing money to buy a home. Lenders base it on the central bank's policy rate, their own funding costs and the risk they see in the borrower. A larger deposit and a good credit history typically earn a lower rate.",
            "A fixed-rate mortgage locks the payment for a set period, which makes budgeting predictable. A variable rate moves with the market, so payments can fall when rates drop but rise sharply when they climb. Many borrowers choose based on how much payment uncertainty their household can absorb.",
            "Because interest compounds over a long term, a one percentage point difference can change total repayments by tens of thousands. Comparing the full cost over the loan's life, including fees, is more useful than looking at the headline rate alone.",
        ],
    },
    {
        "title": "Why Startups Fail, According to Their Founders",
        "category": "Business & Economy",
        "tags": ["Startups", "Entrepreneurship", "Management"],
        "summary": "Running out of money is usually the final symptom, not the cause. Founders' post-mortems point to a handful of recurring mistakes.",
        "body": [
            "When founders write about why their company closed, the most common story is building something people did not need badly enough to pay for. Teams fall in love with a solution and spend months perfecting it before testing whether the underlying problem is real.",
            "Co-founder conflict and hiring too fast follow close behind. Disagreements about direction become expensive once a company has staff and commitments, and payroll can grow faster than revenue during an optimistic fundraising period.",
            "The founders who later succeed tend to describe similar lessons: talk to customers before writing code, charge early, track a small number of honest metrics, and keep enough runway to change direction at least once.",
        ],
    },
    # ------------------------------------------------------------------ Health
    {
        "title": "How Much Sleep Do Adults Really Need?",
        "category": "Health",
        "tags": ["Sleep", "Wellbeing", "Habits"],
        "summary": "Most adults need seven to nine hours, but timing and regularity matter as much as the total.",
        "body": [
            "Sleep researchers broadly agree that most adults function best with seven to nine hours a night. A small minority genuinely need less, but many people who believe they are short sleepers are simply used to feeling tired.",
            "Regular timing helps the body's internal clock. Going to bed and waking up at similar times, even at weekends, makes it easier to fall asleep and leaves people feeling more refreshed than the same number of hours spent at irregular times.",
            "Simple steps improve sleep for many: morning daylight, limiting caffeine after lunch, a cool and dark bedroom, and a wind-down routine without bright screens. Persistent snoring, gasping at night or daytime sleepiness despite enough time in bed are worth discussing with a doctor.",
        ],
    },
    {
        "title": "Walking 30 Minutes a Day: What the Evidence Shows",
        "category": "Health",
        "tags": ["Exercise", "Heart Health", "Wellbeing"],
        "summary": "Brisk walking is one of the most studied and accessible forms of exercise, with benefits for the heart, mood and blood sugar.",
        "body": [
            "Large population studies consistently link regular brisk walking with lower rates of heart disease, type 2 diabetes and early death. Many public health guidelines recommend around 150 minutes of moderate activity per week, which works out to roughly half an hour on most days.",
            "Walking is gentle on joints, requires no equipment and fits easily into daily routines, such as getting off the bus a stop early or taking phone calls on foot. The pace should be quick enough to raise breathing, but still allow a conversation.",
            "The benefits are not only physical. Studies also associate regular walks, especially outdoors and in green spaces, with better mood and lower stress. For people who are currently inactive, even ten-minute walks spread through the day are a meaningful start.",
        ],
    },
    {
        "title": "Understanding Food Labels: Sugar, Salt and Fibre",
        "category": "Health",
        "tags": ["Nutrition", "Diet", "Consumer Advice"],
        "summary": "A minute spent reading the nutrition panel reveals more than the claims on the front of the package.",
        "body": [
            "Front-of-pack slogans such as 'natural' or 'made with whole grains' are marketing; the nutrition table on the back is regulated. Start by checking the serving size, because all other numbers are based on it and it is often smaller than what people actually eat.",
            "Sugar and salt are the two values most worth comparing between similar products. Breakfast cereals, sauces and flavoured yoghurts can vary several-fold. Ingredient lists are ordered by weight, so sugar appearing near the top, sometimes under several different names, is a useful warning sign.",
            "Fibre is the nutrient many diets lack. Choosing breads, cereals and snacks with more fibre per serving supports digestion and helps people feel full for longer. Comparing per 100 grams rather than per serving is the fairest way to judge two products side by side.",
        ],
    },
    {
        "title": "Screen Time and Eye Strain: Practical Tips",
        "category": "Health",
        "tags": ["Eye Health", "Workplace", "Habits"],
        "summary": "Long hours at a screen cause dry, tired eyes for many people. Small changes to habits and workspace help.",
        "body": [
            "Digital eye strain describes a group of symptoms such as dry eyes, blurred vision and headaches after long screen sessions. One cause is that people blink much less often when concentrating on a display, which lets the surface of the eye dry out.",
            "A widely recommended habit is the 20-20-20 rule: every 20 minutes, look at something about 20 feet away for 20 seconds. It relaxes the focusing muscles and reminds you to blink. Positioning the screen slightly below eye level and an arm's length away also helps.",
            "Lighting matters too. Reduce glare from windows, match screen brightness to the room and enlarge text instead of leaning forward. If symptoms persist, an eye test is worthwhile, because an outdated prescription is a common hidden cause.",
        ],
    },
    {
        "title": "The Science of Stress and How to Manage It",
        "category": "Health",
        "tags": ["Mental Health", "Stress", "Wellbeing"],
        "summary": "Short bursts of stress sharpen focus; chronic stress wears the body down. Evidence-based techniques can shift the balance.",
        "body": [
            "When we face a challenge, the body releases hormones such as adrenaline and cortisol that raise heart rate and mobilise energy. That response is useful in short bursts, helping us meet deadlines or react to danger.",
            "Problems arise when the stress response stays switched on for weeks or months. Chronic stress is associated with poor sleep, raised blood pressure, digestive problems and a higher risk of anxiety and depression.",
            "Techniques with good evidence include regular physical activity, slow breathing exercises, structured problem solving and maintaining social contact. When stress feels unmanageable or affects daily life, talking to a doctor or mental health professional is an important step rather than a last resort.",
        ],
    },
    {
        "title": "Hydration Myths: Do You Really Need Eight Glasses?",
        "category": "Health",
        "tags": ["Nutrition", "Hydration", "Myths"],
        "summary": "Fluid needs vary with body size, climate and activity, and much of our water comes from food and other drinks.",
        "body": [
            "The advice to drink eight glasses of water a day is easy to remember but not based on strong evidence. Actual needs vary widely depending on body size, temperature, physical activity and health conditions.",
            "Water also arrives from food, especially fruit, vegetables and soups, and from drinks such as tea, coffee and milk. Despite their reputation, moderate amounts of caffeinated drinks still contribute to daily hydration.",
            "For most healthy adults, thirst is a reliable guide, along with pale yellow urine. Athletes, people working in heat, older adults and anyone who is unwell may need to plan their intake more deliberately.",
        ],
    },
    # ------------------------------------------------------------------ Environment
    {
        "title": "How Heat Pumps Warm a Home Using Outdoor Air",
        "category": "Environment",
        "tags": ["Energy", "Heating", "Climate"],
        "summary": "A heat pump moves heat rather than creating it, which is why it can deliver several units of warmth for each unit of electricity.",
        "body": [
            "Even cold winter air contains heat energy. A heat pump uses a refrigerant that evaporates at very low temperatures, absorbing heat from outside air, ground or water. A compressor then raises the refrigerant's pressure and temperature so that the heat can be released indoors.",
            "Because it moves heat instead of burning fuel, a well-installed heat pump can deliver three or more units of heat for every unit of electricity it consumes. That efficiency is why governments promote them as a way to cut emissions from home heating.",
            "Performance depends on installation. Homes with good insulation and properly sized radiators or underfloor heating get the best results. Installers typically assess heat loss room by room before recommending a model, rather than simply matching the old boiler's output.",
        ],
    },
    {
        "title": "Urban Trees and the Fight Against Heat Islands",
        "category": "Environment",
        "tags": ["Cities", "Climate", "Urban Planning"],
        "summary": "Asphalt and concrete trap heat, making cities several degrees warmer than their surroundings. Trees are one of the most effective natural coolers.",
        "body": [
            "Dense city centres absorb sunlight during the day and release it slowly at night, a phenomenon called the urban heat island. On summer evenings, streets can stay several degrees warmer than nearby countryside, raising health risks during heatwaves.",
            "Trees counter this effect in two ways. Their canopy shades pavements and walls, and they release water vapour through their leaves, which cools the surrounding air. Streets with mature trees can be noticeably cooler at ground level than bare ones.",
            "Many cities now set canopy cover targets and prioritise planting in neighbourhoods that have historically had fewer trees. Choosing species suited to future climates and protecting roots from compacted soil are as important as the number of trees planted.",
        ],
    },
    {
        "title": "Recycling Plastics: What Actually Gets Recycled",
        "category": "Environment",
        "tags": ["Recycling", "Plastic", "Waste"],
        "summary": "The number inside the recycling triangle identifies the resin, not whether your local facility can process it.",
        "body": [
            "Plastics are made from many different polymers, and they cannot simply be melted together. Bottles made from PET and containers made from HDPE are widely recycled because there are established markets for the material. Films, mixed-material pouches and small items are much harder.",
            "Contamination is a major problem. Food residue, liquids and items that do not belong can lower the quality of an entire bale of sorted material. Rinsing containers and following local guidance helps more than putting everything in the bin and hoping it gets sorted.",
            "Recycling is only one part of the solution. Reducing single-use packaging and designing products from a single, recyclable material keep more plastic out of landfills and the environment in the first place.",
        ],
    },
    {
        "title": "Rooftop Solar: Is It Worth It for Your Home?",
        "category": "Environment",
        "tags": ["Solar Power", "Energy", "Personal Finance"],
        "summary": "Payback depends on sunshine, electricity prices and how much power you use during daylight hours.",
        "body": [
            "Solar panel prices have fallen dramatically over the past decade, making rooftop systems affordable for many homeowners. Whether they pay off depends on how much sunlight the roof receives, local electricity prices and what the grid pays for surplus power.",
            "Households that use more electricity during the day, such as those with home offices or electric vehicles charged at midday, benefit most because they use their own generation directly. Battery storage can shift solar energy into the evening but adds significant cost.",
            "Before installing, it is worth checking roof orientation, shading from trees or buildings and the remaining life of the roof itself. Reputable installers provide generation estimates based on local weather data rather than optimistic national averages.",
        ],
    },
    {
        "title": "Why Coral Reefs Bleach and How They Recover",
        "category": "Environment",
        "tags": ["Oceans", "Climate", "Biodiversity"],
        "summary": "Bleaching happens when stressed corals expel the algae that feed them. Recovery is possible, but only if heat stress eases in time.",
        "body": [
            "Reef-building corals live in partnership with microscopic algae that live inside their tissues. The algae provide most of the coral's food through photosynthesis and give reefs their colour.",
            "When water stays unusually warm for weeks, the partnership breaks down and corals expel their algae, turning white. Bleached corals are not dead, but they are starving. If temperatures return to normal quickly, the algae can recolonise and the coral survives.",
            "Repeated bleaching events leave little time for recovery. Scientists are studying heat-tolerant coral strains and restoration techniques, while emphasising that reducing local pollution and global warming remains essential for reefs' long-term survival.",
        ],
    },
    {
        "title": "Composting at Home: A Step-by-Step Guide",
        "category": "Environment",
        "tags": ["Composting", "Gardening", "Waste"],
        "summary": "With the right balance of greens and browns, kitchen scraps turn into rich garden soil in a few months.",
        "body": [
            "Composting relies on microbes that break down organic material. They need a balance of nitrogen-rich 'greens', such as vegetable peelings, coffee grounds and grass clippings, and carbon-rich 'browns', such as dry leaves, cardboard and paper.",
            "A good rule of thumb is roughly equal volumes of greens and browns. Too many greens make a heap slimy and smelly; too many browns slow the process down. Turning the pile every week or two adds oxygen and speeds up decomposition.",
            "Avoid meat, dairy and oily food in a simple home bin, as they attract pests. When the compost is dark, crumbly and smells like earth, it is ready to mix into garden beds or pots.",
        ],
    },
]
