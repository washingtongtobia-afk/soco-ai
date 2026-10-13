"""Deterministic industry configurations for SoCo Agent.

Users should not have to choose their tone or voice. These profiles are
predefined and deterministically assigned based on the business's industry.
Observances are comprehensively mapped from the industry reference dataset
across all 12 calendar months.
"""

from __future__ import annotations

from app.models.industry import IndustryObservance, IndustryProfile, IndustryType


INDUSTRY_PROFILES: dict[IndustryType, IndustryProfile] = {
    IndustryType.CONSTRUCTION_CIVIL_ENGINEERING: IndustryProfile(
        id=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        display_name="Construction / Civil Engineering",
        tone="Professional, confident, and informative",
        voice="Technical, authoritative, and accessible",
        focus_areas=[
            "Infrastructure projects and municipal improvements",
            "Civil and structural engineering developments",
            "Building regulations, codes, and zoning compliance",
            "Job site safety standards and fall protection (OSHA)",
            "Sustainable building materials, LEED, and resilient roofing",
        ],
        recommended_hashtags=[
            "#CivilEngineering",
            "#Infrastructure",
            "#ConstructionSafety",
            "#BuildingBetter",
            "#EngineeringExcellence",
            "#SafetyFirst",
            "#BuiltEnvironment",
        ],
        observances=[
            # January
            IndustryObservance(name="International Public Domain Day", month=1, day=1, description="Blueprints and structural design heritage", keywords=["blueprints", "design", "architecture", "heritage"]),
            IndustryObservance(name="World Braille Day", month=1, day=4, description="Accessible buildings and universal design", keywords=["accessibility", "universal design", "ada", "building"]),
            IndustryObservance(name="National Clean Off Your Desk Day", month=1, day=12, floating_rule="2nd_mon_jan", description="Job site safety and clean work sites", keywords=["safety", "clean", "jobsite", "organized"]),
            # February
            IndustryObservance(name="World Pulses Day", month=2, day=10, description="Sustainable facilities and agri-construction", keywords=["sustainable", "agriculture", "facilities"]),
            IndustryObservance(name="International Day of Women & Girls in Science", month=2, day=11, description="Women in construction and engineering", keywords=["women", "stem", "engineering", "careers"]),
            IndustryObservance(name="National Engineers Week", month=2, day=15, floating_rule="3rd_week_feb", description="Honoring civil and structural engineers", keywords=["engineers", "civil engineering", "structural", "infrastructure"]),
            # March
            IndustryObservance(name="World Wildlife Day", month=3, day=3, description="Eco-friendly building and biodiversity green roofs", keywords=["eco", "green roof", "wildlife", "environmental"]),
            IndustryObservance(name="World Water Day", month=3, day=22, description="Stormwater systems and civil drainage infrastructure", keywords=["water", "stormwater", "drainage", "civil"]),
            IndustryObservance(name="World Meteorological Day", month=3, day=23, description="Roofing, weatherproofing, and building envelopes", keywords=["weatherproofing", "roofing", "envelope", "resilience"]),
            # April
            IndustryObservance(name="National DIY Day", month=4, day=2, description="Professional craftsmanship vs DIY roofing", keywords=["diy", "craftsmanship", "professional", "roofing"]),
            IndustryObservance(name="Earth Day", month=4, day=22, description="Solar roofs, green building, and sustainable materials", keywords=["earth", "solar", "sustainability", "green building"]),
            IndustryObservance(name="Workers' Memorial Day / Safety & Health at Work", month=4, day=28, description="Job site safety and fall protection protocols", keywords=["safety", "fall protection", "osha", "workers"]),
            # May
            IndustryObservance(name="National Skilled Trades Day", month=5, day=6, floating_rule="1st_wed_may", description="Celebrating roofers, masons, and skilled trades", keywords=["trades", "roofers", "craftsmanship", "skills"]),
            IndustryObservance(name="International Day of Light", month=5, day=16, description="Skylights, daylighting, and energy efficiency", keywords=["daylighting", "energy", "skylights", "lighting"]),
            IndustryObservance(name="World Bee Day", month=5, day=20, description="Pollinator-friendly green roofs and urban eco-roofs", keywords=["green roof", "pollinator", "eco", "environment"]),
            # June
            IndustryObservance(name="World Environment Day", month=6, day=5, description="Green building standards and LEED certifications", keywords=["leed", "green building", "environment", "standards"]),
            IndustryObservance(name="World Day to Combat Desertification & Drought", month=6, day=17, description="Erosion control, stormwater BMPs, and soil stability", keywords=["erosion", "stormwater", "soil", "grading"]),
            IndustryObservance(name="International Women in Engineering Day", month=6, day=23, description="Spotlighting women leading civil engineering projects", keywords=["women", "engineering", "stem", "leaders"]),
            # July
            IndustryObservance(name="National Wildland Firefighter Day", month=7, day=2, description="Fire-resistant roofing and building materials", keywords=["fire", "roofing", "materials", "safety"]),
            IndustryObservance(name="World Population Day", month=7, day=11, description="Urbanization and growing infrastructure needs", keywords=["urbanization", "housing", "infrastructure", "growth"]),
            IndustryObservance(name="National Rain Day", month=7, day=29, description="Roof drainage, waterproofing, and leak prevention", keywords=["drainage", "waterproofing", "roof", "maintenance"]),
            # August
            IndustryObservance(name="International Youth Day", month=8, day=12, description="Construction apprenticeships and next-gen builders", keywords=["apprenticeship", "youth", "trades", "training"]),
            IndustryObservance(name="National Thrift Shop Day", month=8, day=17, description="Recycling and reuse of architectural building materials", keywords=["reuse", "salvage", "recycling", "materials"]),
            IndustryObservance(name="National Aviation Day", month=8, day=19, description="Drone surveying and tech-enabled roof inspections", keywords=["drone", "inspection", "technology", "surveying"]),
            # September
            IndustryObservance(name="National Skyscraper Day", month=9, day=3, description="High-rise construction and urban civil engineering", keywords=["skyscraper", "high-rise", "structural", "urban"]),
            IndustryObservance(name="International Coastal Cleanup Day", month=9, day=19, floating_rule="3rd_sat_sep", description="Shoreline infrastructure and coastal erosion control", keywords=["coastal", "erosion", "infrastructure", "marine"]),
            IndustryObservance(name="Falls Prevention Awareness Day", month=9, day=22, description="Roofing and elevated job site fall prevention (OSHA)", keywords=["fall prevention", "roofing", "safety", "osha"]),
            # October
            IndustryObservance(name="World Habitat Day", month=10, day=5, floating_rule="1st_mon_oct", description="Safe, resilient, and affordable housing access", keywords=["housing", "shelter", "community", "residential"]),
            IndustryObservance(name="World Architecture Day", month=10, day=5, floating_rule="1st_mon_oct", description="Design meets build in the modern built environment", keywords=["architecture", "design", "built environment", "commercial"]),
            IndustryObservance(name="International Day for Disaster Risk Reduction", month=10, day=13, description="Resilient construction and storm-tested structural systems", keywords=["disaster", "resilience", "storm", "hurricane"]),
            IndustryObservance(name="World Standards Day", month=10, day=14, description="Building codes, material safety, and engineering standards", keywords=["standards", "codes", "compliance", "quality"]),
            # November
            IndustryObservance(name="World Urbanism Day", month=11, day=8, description="City planning, zoning, and municipal smart infrastructure", keywords=["urban planning", "smart cities", "infrastructure", "zoning"]),
            IndustryObservance(name="America Recycles Day", month=11, day=15, description="Recycling construction waste and shingle materials", keywords=["recycling", "waste", "sustainability", "roofing"]),
            IndustryObservance(name="National Entrepreneurs Day", month=11, day=17, floating_rule="3rd_tue_nov", description="Spotlighting construction and roofing business founders", keywords=["entrepreneurs", "contractors", "business", "startups"]),
            IndustryObservance(name="World Toilet Day", month=11, day=19, description="Sanitation infrastructure and municipal water works", keywords=["sanitation", "water", "plumbing", "civil"]),
            # December
            IndustryObservance(name="World Soil Day", month=12, day=5, description="Geotechnical engineering, site prep, and foundation soil health", keywords=["geotechnical", "soil", "foundation", "site prep"]),
            IndustryObservance(name="National Miners Day", month=12, day=6, description="Raw materials, aggregates, and construction supply chain", keywords=["aggregates", "materials", "mining", "supply chain"]),
            IndustryObservance(name="International Mountain Day", month=12, day=11, description="Steep slope roofing safety and hillside engineering", keywords=["steep slope", "roofing", "slope", "hillside"]),
        ],
        writing_guidelines=[
            "Highlight safety protocols, durability, engineering rigor, and structural integrity.",
            "Explain technical concepts clearly so clients and stakeholders understand project value.",
            "Celebrate team craftsmanship, milestones, and community impact.",
        ],
    ),
    IndustryType.NONPROFIT: IndustryProfile(
        id=IndustryType.NONPROFIT,
        display_name="Nonprofit",
        tone="Compassionate, encouraging, and community-focused",
        voice="Empathetic, informative, and action-oriented",
        focus_areas=[
            "Community needs, housing insecurity, and shelter relief",
            "Food assistance, nutrition programs, and family support",
            "Transparent donor stewardship and impact reporting",
            "Volunteer mobilization and grassroots advocacy",
            "Social policy, equity, and mission-aligned developments",
        ],
        recommended_hashtags=[
            "#CommunityFirst",
            "#NonprofitWork",
            "#SocialImpact",
            "#MakeADifference",
            "#VolunteerPower",
            "#MissionDriven",
            "#NonprofitsCare",
        ],
        observances=[
            # January
            IndustryObservance(name="National Blood Donor Month", month=1, day=1, description="Encouraging life-saving community blood donations", keywords=["blood", "health", "donation", "community"]),
            IndustryObservance(name="National Human Trafficking Awareness Day", month=1, day=11, description="Raising awareness and supporting survivor rehabilitation", keywords=["trafficking", "awareness", "survivors", "protection"]),
            IndustryObservance(name="Martin Luther King Jr. Day of Service", month=1, day=19, floating_rule="3rd_mon_jan", description="Commemorating Dr. King through community volunteerism", keywords=["service", "mlk", "civil rights", "volunteers"]),
            # February
            IndustryObservance(name="World Cancer Day", month=2, day=4, description="Advocacy, health equity, and patient family support", keywords=["cancer", "health", "advocacy", "support"]),
            IndustryObservance(name="International Day of Women & Girls in Science", month=2, day=11, description="Equity in education and STEM empowerment for girls", keywords=["stem", "women", "education", "equity"]),
            IndustryObservance(name="World Day of Social Justice", month=2, day=20, description="Championing equitable access, housing, and social security", keywords=["social justice", "equity", "poverty", "rights"]),
            # March
            IndustryObservance(name="International Women’s Day", month=3, day=8, description="Celebrating women changemakers and gender empowerment", keywords=["women", "empowerment", "equity", "leadership"]),
            IndustryObservance(name="World Down Syndrome Day", month=3, day=21, description="Advocating for inclusion, dignity, and family support", keywords=["inclusion", "disability", "family", "advocacy"]),
            IndustryObservance(name="World Water Day", month=3, day=22, description="Ensuring access to clean water and sanitation for all", keywords=["water", "health", "basic needs", "poverty"]),
            # April
            IndustryObservance(name="World Autism Awareness Day", month=4, day=2, description="Neurodiversity acceptance and community support services", keywords=["autism", "neurodiversity", "acceptance", "inclusion"]),
            IndustryObservance(name="World Health Day", month=4, day=7, description="Spotlighting community clinics and wellness access", keywords=["health", "wellness", "clinics", "healthcare"]),
            IndustryObservance(name="National Volunteer Month", month=4, day=15, description="Recognizing and mobilizing community volunteers", keywords=["volunteers", "service", "community", "helping"]),
            IndustryObservance(name="Earth Day", month=4, day=22, description="Environmental justice, neighborhood cleanups, and sustainability", keywords=["earth", "environment", "clean up", "climate"]),
            # May
            IndustryObservance(name="National Foster Care Month", month=5, day=1, description="Supporting foster youth, kinship families, and caseworkers", keywords=["foster care", "youth", "children", "families"]),
            IndustryObservance(name="International Day of Families", month=5, day=15, description="Strengthening family stability and community care networks", keywords=["families", "housing", "support", "stability"]),
            IndustryObservance(name="World Hunger Day", month=5, day=28, description="Spotlighting food insecurity and nutrition support programs", keywords=["hunger", "food", "pantry", "nutrition"]),
            # June
            IndustryObservance(name="World Environment Day", month=6, day=5, description="Grassroots environmental initiatives and neighborhood resilience", keywords=["environment", "neighborhood", "sustainability"]),
            IndustryObservance(name="International Day Against Child Labor", month=6, day=12, description="Protecting vulnerable children and expanding educational access", keywords=["children", "rights", "education", "protection"]),
            IndustryObservance(name="World Refugee Day", month=6, day=20, description="Welcoming displaced families with shelter and resources", keywords=["refugee", "displaced", "shelter", "welcome"]),
            # July
            IndustryObservance(name="World Population Day", month=7, day=11, description="Advancing health equity, shelter access, and human rights", keywords=["population", "equity", "housing", "community"]),
            IndustryObservance(name="World Youth Skills Day", month=7, day=15, description="Job readiness, mentorship, and career training for youth", keywords=["youth", "skills", "mentorship", "jobs"]),
            IndustryObservance(name="Nelson Mandela International Day", month=7, day=18, description="Inspiring 67 minutes of public community service", keywords=["service", "justice", "mandela", "community"]),
            # August
            IndustryObservance(name="International Youth Day", month=8, day=12, description="Celebrating young community leaders and advocates", keywords=["youth", "leadership", "advocacy", "empowerment"]),
            IndustryObservance(name="National Nonprofit Day", month=8, day=17, description="Honoring nonprofit impact and grassroots organizations", keywords=["nonprofit", "impact", "mission", "charity"]),
            IndustryObservance(name="World Humanitarian Day", month=8, day=19, description="Honoring frontline aid workers and disaster responders", keywords=["humanitarian", "relief", "aid", "first responders"]),
            IndustryObservance(name="International Day for the Remembrance of the Slave Trade", month=8, day=23, description="Racial justice, civil rights education, and historical equity", keywords=["racial justice", "equity", "civil rights", "history"]),
            # September
            IndustryObservance(name="International Day of Charity", month=9, day=5, description="Inspiring charitable donations, volunteerism, and service", keywords=["charity", "giving", "donations", "support"]),
            IndustryObservance(name="International Day of Peace", month=9, day=21, description="Fostering community harmony, dialogue, and conflict resolution", keywords=["peace", "dialogue", "community", "harmony"]),
            IndustryObservance(name="World Alzheimer’s Day", month=9, day=21, description="Supporting family caregivers and memory care resources", keywords=["alzheimers", "caregivers", "health", "seniors"]),
            # October
            IndustryObservance(name="World Smile Day", month=10, day=2, floating_rule="1st_fri_oct", description="Spreading compassion, kindness, and neighborly warmth", keywords=["kindness", "compassion", "smile", "warmth"]),
            IndustryObservance(name="World Mental Health Day", month=10, day=10, description="Mental wellness resources and destigmatizing care", keywords=["mental health", "wellness", "support", "counseling"]),
            IndustryObservance(name="World Food Day", month=10, day=16, description="Ending food insecurity and expanding community meal programs", keywords=["food", "hunger", "meals", "pantry"]),
            # November
            IndustryObservance(name="Hunger & Homelessness Awareness Week", month=11, day=15, floating_rule="mid_nov", description="Spotlighting housing insecurity and shelter relief", keywords=["housing", "homelessness", "shelter", "poverty", "hunger"]),
            IndustryObservance(name="International Day for Tolerance", month=11, day=16, description="Promoting inclusion, diversity, and community respect", keywords=["tolerance", "inclusion", "diversity", "equity"]),
            IndustryObservance(name="International Students Day", month=11, day=17, description="Educational access and youth scholarship support", keywords=["students", "education", "youth", "schools"]),
            # November / December Floating
            IndustryObservance(name="Giving Tuesday", month=11, day=24, floating_rule="tue_post_thanksgiving", description="Global day of community generosity and charitable giving", keywords=["giving", "donations", "fundraising", "generosity", "nonprofit"]),
            # December
            IndustryObservance(name="International Day of Persons with Disabilities", month=12, day=3, description="Accessibility rights, adaptive resources, and inclusion", keywords=["disability", "accessibility", "inclusion", "rights"]),
            IndustryObservance(name="International Volunteer Day", month=12, day=5, description="Celebrating community volunteers and grassroots changemakers", keywords=["volunteers", "thank you", "service", "helpers"]),
            IndustryObservance(name="Human Rights Day", month=12, day=10, description="Defending dignity, equal rights, and justice for all people", keywords=["human rights", "justice", "dignity", "advocacy"]),
        ],
        writing_guidelines=[
            "Lead with empathy, dignity, and real human impact.",
            "Clearly communicate specific ways followers can help: donate, volunteer, share, or advocate.",
            "Celebrate community partners, volunteers, and gratitude for ongoing support.",
        ],
    ),
    IndustryType.RESTAURANT: IndustryProfile(
        id=IndustryType.RESTAURANT,
        display_name="Restaurant",
        tone="Friendly, engaging, and conversational",
        voice="Welcoming, energetic, and promotional",
        focus_areas=[
            "Fresh ingredients, sourcing transparency, and kitchen craftsmanship",
            "Food safety, sanitation protocols, and quality standards",
            "Signature dishes, daily specials, and chef-curated menus",
            "Local dining culture, events, and community hospitality",
            "Seasonal drink pairings, desserts, and holiday dining",
        ],
        recommended_hashtags=[
            "#EatLocal",
            "#FoodieLife",
            "#DailySpecials",
            "#CulinaryCraft",
            "#FreshIngredients",
            "#DiningExperience",
            "#CafeVibes",
        ],
        observances=[
            # January
            IndustryObservance(name="National Soup Month", month=1, day=1, description="Warm seasonal soups and comfort food pairings", keywords=["soup", "comfort food", "warm", "lunch"]),
            IndustryObservance(name="National Spaghetti Day", month=1, day=4, description="Classic pasta dishes and Italian specialties", keywords=["pasta", "spaghetti", "italian", "dinner"]),
            IndustryObservance(name="National Bagel Day", month=1, day=15, description="Fresh breakfast bagels, spreads, and morning coffee", keywords=["bagel", "breakfast", "coffee", "morning"]),
            IndustryObservance(name="National Croissant Day", month=1, day=30, description="Buttery fresh pastries and artisan bakery treats", keywords=["croissant", "bakery", "pastry", "breakfast"]),
            # February
            IndustryObservance(name="National Pizza Day", month=2, day=9, description="Signature artisan pizzas and slice specials", keywords=["pizza", "crust", "slice", "dinner"]),
            IndustryObservance(name="World Pulses Day", month=2, day=10, description="Healthy beans, lentils, and plant-forward menu options", keywords=["beans", "lentils", "healthy", "vegan"]),
            IndustryObservance(name="National Drink Wine Day", month=2, day=18, description="Curated wine pairings, tasting flights, and dinner service", keywords=["wine", "drinks", "pairings", "dinner"]),
            IndustryObservance(name="National Chili Day", month=2, day=26, floating_rule="4th_thu_feb", description="Hearty chili bowls, cornbread, and house spices", keywords=["chili", "comfort food", "spicy", "lunch"]),
            # March
            IndustryObservance(name="National Pancake Day", month=3, day=4, description="Fluffy pancakes, breakfast stacks, and maple syrup", keywords=["pancakes", "breakfast", "brunch", "morning"]),
            IndustryObservance(name="National Meatball Day", month=3, day=9, description="House-made meatballs, savory sauces, and family plates", keywords=["meatball", "italian", "dinner", "family"]),
            IndustryObservance(name="World Water Day", month=3, day=22, description="Safe kitchen water filtration and sustainable dining", keywords=["water", "safe dining", "kitchen", "pure"]),
            IndustryObservance(name="National Chip & Dip Day", month=3, day=23, description="House-made tortilla chips, salsa, guac, and queso", keywords=["chips", "dip", "salsa", "appetizer"]),
            # April
            IndustryObservance(name="National Burrito Day", month=4, day=2, floating_rule="1st_thu_apr", description="Stuffed burritos, fresh bowls, and lunchtime favorites", keywords=["burrito", "mexican", "lunch", "specials"]),
            IndustryObservance(name="World Health Day", month=4, day=7, description="Nutritious dining, fresh greens, and balanced meals", keywords=["healthy", "salads", "nutrition", "fresh"]),
            IndustryObservance(name="National Grilled Cheese Sandwich Day", month=4, day=12, description="Gourmet melted cheese sandwiches and tomato soup", keywords=["grilled cheese", "sandwich", "cheese", "lunch"]),
            IndustryObservance(name="National Pretzel Day", month=4, day=26, description="Warm baked pretzels, beer cheese, and mustard dips", keywords=["pretzel", "beer", "appetizer", "bakery"]),
            # May
            IndustryObservance(name="National Pizza Party Day", month=5, day=15, floating_rule="3rd_fri_may", description="Pizza celebrations, family deals, and group catering", keywords=["pizza", "party", "catering", "family"]),
            IndustryObservance(name="National Burger Day", month=5, day=28, description="Juicy craft burgers, toppings, and crisp fries", keywords=["burger", "fries", "beef", "lunch"]),
            IndustryObservance(name="National Brisket Day", month=5, day=28, description="Slow-smoked brisket, BBQ sauces, and tender cuts", keywords=["brisket", "bbq", "smoked", "meat"]),
            IndustryObservance(name="World Hunger Day", month=5, day=28, description="Partnering with local food banks to end food waste", keywords=["hunger", "community", "food bank", "charity"]),
            # June
            IndustryObservance(name="National Donut Day", month=6, day=5, floating_rule="1st_fri_jun", description="Artisan donuts, sweet glazes, and morning coffee", keywords=["donut", "sweet", "coffee", "pastry"]),
            IndustryObservance(name="World Food Safety Day", month=6, day=7, description="Clean kitchen protocols, food safety, and guest trust", keywords=["food safety", "clean", "hygiene", "standards"]),
            IndustryObservance(name="National Iced Tea Day", month=6, day=10, description="Fresh brewed iced tea, lemonade, and summer drinks", keywords=["iced tea", "tea", "beverages", "summer"]),
            IndustryObservance(name="National Sushi Day", month=6, day=18, description="Fresh sashimi, specialty rolls, and Japanese culinary art", keywords=["sushi", "japanese", "rolls", "seafood"]),
            # July
            IndustryObservance(name="World Chocolate Day", month=7, day=7, description="Decadent chocolate desserts, cakes, and artisan pastries", keywords=["chocolate", "dessert", "cake", "sweet"]),
            IndustryObservance(name="World Population Day", month=7, day=11, description="Celebrating global culinary heritage and diverse cuisines", keywords=["global", "flavors", "cuisine", "culture"]),
            IndustryObservance(name="National Hot Dog Day", month=7, day=15, floating_rule="3rd_wed_jul", description="Summer hot dogs, specialty sausages, and toppings", keywords=["hot dog", "summer", "bbq", "grill"]),
            IndustryObservance(name="National Ice Cream Day", month=7, day=19, floating_rule="3rd_sun_jul", description="Handcrafted ice cream scoops, sundaes, and cool treats", keywords=["ice cream", "dessert", "summer", "scoops"]),
            # August
            IndustryObservance(name="National Watermelon Day", month=8, day=3, description="Refreshing summer salads, craft mocktails, and seasonal fruit", keywords=["watermelon", "summer", "cocktails", "fresh"]),
            IndustryObservance(name="National Filet Mignon Day", month=8, day=13, description="Prime cuts, fine steakhouse dinners, and chef specials", keywords=["steak", "filet mignon", "fine dining", "dinner"]),
            IndustryObservance(name="World Humanitarian Day", month=8, day=19, description="Cafes and restaurants supporting local community meals", keywords=["community", "giving", "humanitarian", "charity"]),
            IndustryObservance(name="National Toasted Marshmallow Day", month=8, day=30, description="Campfire desserts, s'mores treats, and sweet endings", keywords=["marshmallow", "dessert", "sweet", "campfire"]),
            # September
            IndustryObservance(name="National Cheese Pizza Day", month=9, day=5, description="Classic mozzarella pies, marinara, and fresh basil", keywords=["pizza", "cheese", "italian", "dinner"]),
            IndustryObservance(name="International Day of Charity", month=9, day=5, description="Food bank partnerships and community hunger relief", keywords=["charity", "food bank", "community", "giving"]),
            IndustryObservance(name="National Guacamole Day", month=9, day=16, description="Fresh mashed avocado, cilantro, lime, and tortilla chips", keywords=["guacamole", "avocado", "mexican", "appetizer"]),
            IndustryObservance(name="National Coffee Day", month=9, day=29, description="Celebrating coffee lovers, espresso shots, and cold brew", keywords=["coffee", "espresso", "latte", "cafe"]),
            # October
            IndustryObservance(name="International Coffee Day", month=10, day=1, description="Single-origin roasts, barista craft, and latte art", keywords=["coffee", "barista", "latte", "cafe"]),
            IndustryObservance(name="National Taco Day", month=10, day=4, description="Street tacos, salsa verde, carnitas, and margarita deals", keywords=["taco", "mexican", "margarita", "dinner"]),
            IndustryObservance(name="National Dessert Day", month=10, day=14, description="Chef's signature desserts, cheesecakes, and sweet bites", keywords=["dessert", "sweet", "bakery", "cake"]),
            IndustryObservance(name="World Food Day", month=10, day=16, description="Sustainable ingredient sourcing and eliminating food waste", keywords=["sustainable", "sourcing", "food waste", "dining"]),
            # November
            IndustryObservance(name="National Sandwich Day", month=11, day=3, description="Artisan subs, paninis, club sandwiches, and lunch deals", keywords=["sandwich", "panini", "lunch", "deli"]),
            IndustryObservance(name="National Cappuccino Day", month=11, day=8, description="Steamed milk foam, bold espresso, and cozy cafe vibes", keywords=["cappuccino", "coffee", "cafe", "espresso"]),
            IndustryObservance(name="America Recycles Day", month=11, day=15, description="Composting, eco-friendly takeout containers, and green dining", keywords=["recycling", "sustainable", "takeout", "eco"]),
            IndustryObservance(name="National Espresso Day", month=11, day=23, description="Rich espresso crema, afternoon pick-me-ups, and affogatos", keywords=["espresso", "coffee", "energy", "cafe"]),
            # December
            IndustryObservance(name="National Cookie Day", month=12, day=4, description="Warm baked chocolate chip cookies, holiday boxes, and treats", keywords=["cookie", "bakery", "dessert", "holiday"]),
            IndustryObservance(name="International Volunteer Day", month=12, day=5, description="Serving holiday meals with local hunger relief shelters", keywords=["volunteer", "community", "meals", "charity"]),
            IndustryObservance(name="National Brownie Day", month=12, day=8, description="Fudgy gourmet brownies, walnut bars, and ice cream pairings", keywords=["brownie", "chocolate", "dessert", "bakery"]),
            IndustryObservance(name="National Hot Chocolate Day", month=12, day=31, description="Rich hot cocoa, whipped cream, and cozy winter warmers", keywords=["hot chocolate", "cocoa", "winter", "beverage"]),
        ],
        writing_guidelines=[
            "Evoke appetizing sensory details, fresh aromas, and inviting ambience.",
            "Create excitement around seasonal ingredients, pairing suggestions, and chef specials.",
            "Foster community by inviting guests to comment, tag dining companions, and visit.",
        ],
    ),
    IndustryType.LAW_OFFICE: IndustryProfile(
        id=IndustryType.LAW_OFFICE,
        display_name="Law Office",
        tone="Professional, reassuring, and informative",
        voice="Authoritative, trustworthy, and clear",
        focus_areas=[
            "Newly enacted statutes, effective dates, and statutory compliance",
            "Contractual protections, commercial governance, and liability mitigation",
            "Appellate court decisions, binding precedents, and regulatory rulings",
            "Individual rights, family protections, and estate planning peace of mind",
            "Clear educational legal guidance distinguishing proposed bills from law",
        ],
        recommended_hashtags=[
            "#LegalInsights",
            "#KnowYourRights",
            "#LawOffice",
            "#LegalUpdate",
            "#ComplianceAlert",
            "#LegalGuidance",
            "#RuleOfLaw",
        ],
        observances=[
            # January
            IndustryObservance(name="Emancipation Proclamation Anniversary", month=1, day=1, description="Historic milestone in constitutional rights and liberty", keywords=["constitution", "freedom", "history", "rights"]),
            IndustryObservance(name="Law Enforcement Appreciation Day", month=1, day=9, description="Honoring officers, bailiffs, and criminal justice professionals", keywords=["justice", "court", "law enforcement", "officers"]),
            IndustryObservance(name="Martin Luther King Jr. Day", month=1, day=19, floating_rule="3rd_mon_jan", description="Reflecting on civil rights jurisprudence and equal protection", keywords=["civil rights", "equal protection", "justice", "constitution"]),
            # February
            IndustryObservance(name="National Freedom Day", month=2, day=1, description="Celebrating constitutional freedom under the 13th Amendment", keywords=["freedom", "constitution", "amendment", "rights"]),
            IndustryObservance(name="Rosa Parks Day", month=2, day=4, description="Pivotal civil rights litigation challenging segregation laws", keywords=["civil rights", "litigation", "equality", "courts"]),
            IndustryObservance(name="World Day of Social Justice", month=2, day=20, description="Equal protection of the laws, fair trials, and systemic equity", keywords=["social justice", "equal rights", "due process", "fairness"]),
            # March
            IndustryObservance(name="International Women’s Day", month=3, day=8, description="Women's legal equality, workplace statutes, and civil protections", keywords=["women", "equality", "workplace", "employment law"]),
            IndustryObservance(name="International Day for the Elimination of Racial Discrimination", month=3, day=21, description="Combating discrimination under civil rights law", keywords=["discrimination", "civil rights", "compliance", "law"]),
            IndustryObservance(name="World Backup Day", month=3, day=31, description="Data privacy, cybersecurity compliance, and client privilege", keywords=["cyber law", "privacy", "data protection", "confidentiality"]),
            # April
            IndustryObservance(name="International Day for Mine Awareness", month=4, day=4, description="International humanitarian law and civilian protections", keywords=["international law", "treaties", "protection", "justice"]),
            IndustryObservance(name="World Intellectual Property Day", month=4, day=26, description="Protecting trademarks, patents, copyrights, and trade secrets", keywords=["intellectual property", "trademarks", "copyrights", "patents", "ip"]),
            IndustryObservance(name="Workers' Memorial Day", month=4, day=28, description="Workplace safety statutes, OSHA regulations, and worker protections", keywords=["workers comp", "osha", "labor law", "employment"]),
            # May
            IndustryObservance(name="Law Day", month=5, day=1, description="Nationwide celebration of the rule of law and constitutional order", keywords=["law day", "rule of law", "justice", "legal system"]),
            IndustryObservance(name="World Press Freedom Day", month=5, day=3, description="First Amendment protections, free speech, and constitutional rights", keywords=["first amendment", "free speech", "constitution", "press"]),
            IndustryObservance(name="International Day of Families", month=5, day=15, description="Family law protections, estate planning, and child custody safeguards", keywords=["family law", "estate planning", "custody", "probate"]),
            # June
            IndustryObservance(name="World Day Against Child Labor", month=6, day=12, description="Enforcing child protection statutes and statutory labor standards", keywords=["labor law", "child protection", "statutes", "compliance"]),
            IndustryObservance(name="World Refugee Day", month=6, day=20, description="Immigration law, asylum protections, and international due process", keywords=["immigration", "asylum", "refugee", "due process"]),
            IndustryObservance(name="UN Charter Day", month=6, day=26, description="Founding document of international law and sovereign dispute resolution", keywords=["un charter", "international law", "treaty", "dispute"]),
            # July
            IndustryObservance(name="World Population Day", month=7, day=11, description="Legal protections, human rights covenants, and civic equality", keywords=["human rights", "civil liberties", "equality", "law"]),
            IndustryObservance(name="World Day for International Justice", month=7, day=17, description="Honoring international criminal justice and global rule of law", keywords=["international justice", "icc", "courts", "prosecution"]),
            IndustryObservance(name="Nelson Mandela International Day", month=7, day=18, description="Civil rights leadership and peaceful advocacy for equality", keywords=["civil rights", "equality", "justice", "human rights"]),
            # August
            IndustryObservance(name="International Day of the World’s Indigenous Peoples", month=8, day=9, description="Tribal sovereignty, treaty law, and indigenous rights", keywords=["tribal law", "sovereignty", "indigenous", "treaties"]),
            IndustryObservance(name="World Humanitarian Day", month=8, day=19, description="Humanitarian law, international conventions, and legal aid", keywords=["humanitarian law", "legal aid", "justice", "conventions"]),
            IndustryObservance(name="International Day for the Remembrance of the Slave Trade", month=8, day=23, description="Abolition legal history and the evolution of civil liberties", keywords=["civil liberties", "history", "equal protection", "law"]),
            # September
            IndustryObservance(name="International Day of Democracy", month=9, day=15, description="Voting rights statutes, civic participation, and constitutional law", keywords=["voting rights", "democracy", "constitutional", "elections"]),
            IndustryObservance(name="Constitution Day and Citizenship Day", month=9, day=17, description="Commemorating the signing of the U.S. Constitution in 1787", keywords=["constitution", "citizenship", "rights", "founding"]),
            IndustryObservance(name="International Day of Peace", month=9, day=21, description="Dispute resolution, mediation, arbitration, and rule of law", keywords=["mediation", "arbitration", "dispute resolution", "peace"]),
            IndustryObservance(name="International Day of Sign Languages", month=9, day=23, description="Americans with Disabilities Act (ADA) and equal court access", keywords=["ada", "accessibility", "disability rights", "court access"]),
            # October
            IndustryObservance(name="International Day of Non-Violence", month=10, day=2, description="Peaceful civil rights advocacy and constitutional justice", keywords=["civil rights", "peace", "justice", "advocacy"]),
            IndustryObservance(name="World Standards Day", month=10, day=14, description="Regulatory compliance, ethical standards, and legal best practices", keywords=["compliance", "regulations", "ethics", "standards"]),
            IndustryObservance(name="National Pro Bono Week", month=10, day=20, floating_rule="3rd_week_oct", description="Honoring volunteer lawyers expanding equal access to justice", keywords=["pro bono", "legal aid", "access to justice", "volunteers"]),
            IndustryObservance(name="United Nations Day", month=10, day=24, description="International law, multilateral treaties, and global jurisprudence", keywords=["united nations", "international law", "treaties", "global"]),
            # November
            IndustryObservance(name="World Freedom Day", month=11, day=9, description="Democratic rule of law and constitutional protections against overreach", keywords=["freedom", "rule of law", "constitution", "civil rights"]),
            IndustryObservance(name="International Day for Tolerance", month=11, day=16, description="Anti-discrimination statutes, equal protection, and fair employment", keywords=["anti-discrimination", "equal protection", "employment law", "civil rights"]),
            IndustryObservance(name="World Philosophy Day", month=11, day=19, floating_rule="3rd_thu_nov", description="Roots of legal ethics, jurisprudence, and moral principles in law", keywords=["jurisprudence", "ethics", "legal philosophy", "principles"]),
            # December
            IndustryObservance(name="International Day for the Abolition of Slavery", month=12, day=2, description="Combating labor trafficking and human rights violations", keywords=["trafficking", "labor law", "human rights", "criminal law"]),
            IndustryObservance(name="Human Rights Day", month=12, day=10, description="Universal Declaration of Human Rights and fundamental freedoms", keywords=["human rights", "civil liberties", "due process", "freedoms"]),
            IndustryObservance(name="International Human Solidarity Day", month=12, day=20, description="Access to justice, equal legal representation, and dignity under law", keywords=["equal justice", "representation", "due process", "solidarity"]),
        ],
        writing_guidelines=[
            "Distinguish proposed legislation from enacted, effective laws clearly.",
            "Break down complex legal jargon into understandable, actionable insights.",
            "Include responsible informational disclosures (educational content, not individualized legal advice).",
        ],
    ),
}


def get_industry_profile(industry: IndustryType | str) -> IndustryProfile:
    """Retrieve the deterministic industry profile for a given industry.

    Raises:
        ValueError: If the industry cannot be recognized.
    """
    if isinstance(industry, str):
        industry_enum = IndustryType.from_str(industry)
    else:
        industry_enum = industry

    profile = INDUSTRY_PROFILES.get(industry_enum)
    if not profile:
        raise ValueError(f"No profile configured for industry: {industry_enum}")
    return profile


def list_supported_industries() -> list[IndustryProfile]:
    """Return all supported industry profiles."""
    return list(INDUSTRY_PROFILES.values())
