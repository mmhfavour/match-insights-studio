"""Deterministic overlay copy in English, Hindi and Tamil.

These templates are the safety net under the agents: they render any moment for any profile in
microseconds, they only ever use numbers and names that are in the moment's evidence, and they are
what airs when the model is unavailable, slow, or fails verification.

Player, club and team names stay in Latin script in every language, which keeps them consistent with
on-screen graphics and lets the Verifier check them.
"""

from __future__ import annotations

LANGS = ("en", "hi", "ta")
MODES = ("analyst", "casual", "player")

P: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------------- words
    "saved": {"en": "saved", "hi": "बचाया गया", "ta": "தடுக்கப்பட்டது"},
    "off_target": {"en": "off target", "hi": "निशाने से बाहर", "ta": "இலக்கைத் தவறியது"},
    "blocked": {"en": "blocked", "hi": "ब्लॉक हुआ", "ta": "தடுக்கப்பட்டது"},
    "woodwork": {"en": "off the woodwork", "hi": "पोस्ट से टकराया", "ta": "கம்பத்தில் பட்டது"},
    "goal_word": {"en": "scored", "hi": "गोल", "ta": "கோல்"},
    "fading": {"en": "fading", "hi": "कमज़ोर पड़ा", "ta": "குறைகிறது"},
    "rising": {"en": "rising", "hi": "तेज़ हुआ", "ta": "அதிகரிக்கிறது"},
    "control": {"en": "control", "hi": "नियंत्रण", "ta": "கட்டுப்பாடு"},
    "chaos": {"en": "chaos", "hi": "अफ़रा-तफ़री", "ta": "குழப்பம்"},
    "contested": {"en": "contested", "hi": "बराबरी", "ta": "சமநிலை"},
    "yellow": {"en": "Yellow", "hi": "पीला", "ta": "மஞ்சள்"},
    "red": {"en": "Red", "hi": "लाल", "ta": "சிவப்பு"},
    # ---------------------------------------------------------------- perspective (favourite club)
    "persp_good": {"en": "Good news, {club} fans.", "hi": "{club} फैंस के लिए अच्छी खबर।",
                   "ta": "{club} ரசிகர்களுக்கு நல்ல செய்தி."},
    "persp_bad": {"en": "Worry for {club}.", "hi": "{club} के लिए चिंता।", "ta": "{club} அணிக்கு கவலை."},
    "persp_relief": {"en": "Let-off for {club}.", "hi": "{club} बाल-बाल बचा।", "ta": "{club} நூலிழையில் தப்பியது."},
    "persp_close": {"en": "So near for {club}.", "hi": "{club} इतने करीब।", "ta": "{club} மிக அருகில் வந்தது."},
    # ---------------------------------------------------------------- goal
    "goal_h_an": {"en": "{scorer} scores · {score_home}-{score_away}", "hi": "{scorer} का गोल · {score_home}-{score_away}",
                  "ta": "{scorer} கோல் · {score_home}-{score_away}"},
    "goal_b_an": {"en": "xG {xg} · {shot_speed_kmh} km/h from {distance_m} m · {chain_passes} passes in {chain_seconds}s.",
                  "hi": "xG {xg} · {distance_m} मीटर से {shot_speed_kmh} km/h · {chain_seconds} सेकंड में {chain_passes} पास।",
                  "ta": "xG {xg} · {distance_m} மீ தூரத்திலிருந்து {shot_speed_kmh} km/h · {chain_seconds} வினாடியில் {chain_passes} பாஸ்."},
    "goal_h_ca": {"en": "GOAL! {scorer}", "hi": "गोल! {scorer}", "ta": "கோல்! {scorer}"},
    "goal_b_ca": {"en": "{home_name} {score_home}-{score_away} {away_name}.", "hi": "{home_name} {score_home}-{score_away} {away_name}।",
                  "ta": "{home_name} {score_home}-{score_away} {away_name}."},
    "why_patient_an": {"en": "Why it matters: {chain_passes} completed passes pulled the block apart before the finish.",
                       "hi": "क्यों अहम: फ़िनिश से पहले {chain_passes} सटीक पासों ने डिफ़ेंस को खोल दिया।",
                       "ta": "ஏன் முக்கியம்: முடிப்பதற்கு முன் {chain_passes} துல்லியமான பாஸ்கள் தடுப்பைப் பிளந்தன."},
    "why_patient_ca": {"en": "A lovely team move, {chain_passes} passes long.", "hi": "{chain_passes} पासों वाली शानदार टीम मूव।",
                       "ta": "{chain_passes} பாஸ்கள் கொண்ட அழகான அணி நகர்வு."},
    "why_counter_an": {"en": "Why it matters: {regain_player} won it back high; shot {chain_seconds}s later.",
                       "hi": "क्यों अहम: {regain_player} ने ऊपर गेंद छीनी; {chain_seconds} सेकंड बाद शॉट।",
                       "ta": "ஏன் முக்கியம்: {regain_player} மேலே பந்தை மீட்டார்; {chain_seconds} வினாடியில் ஷாட்."},
    "why_counter_ca": {"en": "They stole the ball near goal and scored {chain_seconds} seconds later.",
                       "hi": "गोल के पास गेंद छीनी और {chain_seconds} सेकंड में गोल।",
                       "ta": "கோல் அருகே பந்தைப் பறித்து {chain_seconds} வினாடியில் கோல்."},
    "why_lowxg_an": {"en": "Why it matters: only {xg} xG, so this was execution, not chance quality.",
                     "hi": "क्यों अहम: सिर्फ़ {xg} xG, यानी मौका नहीं, शॉट की क्वालिटी।",
                     "ta": "ஏன் முக்கியம்: வெறும் {xg} xG; வாய்ப்பு அல்ல, ஷாட்டின் தரம்."},
    "why_lowxg_ca": {"en": "An unstoppable {shot_speed_kmh} km/h strike from {distance_m} metres.",
                     "hi": "{distance_m} मीटर से {shot_speed_kmh} km/h का ज़बरदस्त शॉट।",
                     "ta": "{distance_m} மீட்டரிலிருந்து {shot_speed_kmh} km/h அதிரடி ஷாட்."},
    "rel_press_an": {"en": "Context: {related_pressing_team_name} press had dropped to {related_press_rate_now} from {related_press_rate_before}.",
                     "hi": "संदर्भ: {related_pressing_team_name} का प्रेस {related_press_rate_before} से गिरकर {related_press_rate_now} हो गया था।",
                     "ta": "பின்னணி: {related_pressing_team_name} அழுத்தம் {related_press_rate_before} இலிருந்து {related_press_rate_now} ஆகக் குறைந்திருந்தது."},
    "rel_press_ca": {"en": "{related_pressing_team_name} had stopped pressing, and it cost them.",
                     "hi": "{related_pressing_team_name} ने दबाव बनाना छोड़ दिया था, और कीमत चुकाई।",
                     "ta": "{related_pressing_team_name} அழுத்தம் கொடுப்பதை நிறுத்தியது; அதற்கு விலை கொடுத்தது."},
    "rel_mom_an": {"en": "Context: scored during a spell with {related_threat_share_now}% of the threat.",
                   "hi": "संदर्भ: गोल तब आया जब {related_threat_share_now}% खतरा इसी टीम का था।",
                   "ta": "பின்னணி: {related_threat_share_now}% அச்சுறுத்தல் இந்த அணியிடம் இருந்த நேரத்தில் கோல்."},
    "rel_mom_ca": {"en": "They had been on top, and it paid off.", "hi": "वे हावी थे, और मेहनत रंग लाई।",
                   "ta": "அவர்கள் ஆதிக்கம் செலுத்தினர்; பலன் கிடைத்தது."},
    # ---------------------------------------------------------------- big chance
    "big_h_an": {"en": "Big chance · {player}", "hi": "बड़ा मौका · {player}", "ta": "பெரிய வாய்ப்பு · {player}"},
    "big_b_an": {"en": "{xg} xG from {distance_m} m, {outcome_t}. {team_name} so far: {team_xg} xG, goals {team_goals}.",
                 "hi": "{distance_m} मीटर से {xg} xG, {outcome_t}। {team_name}: {team_xg} xG, {team_goals} गोल।",
                 "ta": "{distance_m} மீ தூரத்தில் {xg} xG, {outcome_t}. {team_name}: {team_xg} xG, {team_goals} கோல்."},
    "big_h_ca": {"en": "So close for {player}!", "hi": "{player} चूक गए!", "ta": "{player} நூலிழையில் தவறவிட்டார்!"},
    "big_b_ca": {"en": "From {distance_m} metres, a chance that goes in about {xg_pct}% of the time.",
                 "hi": "{distance_m} मीटर से ऐसा मौका लगभग {xg_pct}% बार गोल बनता है।",
                 "ta": "{distance_m} மீட்டரிலிருந்து இப்படிப்பட்ட வாய்ப்பு சுமார் {xg_pct}% முறை கோலாகும்."},
    # ---------------------------------------------------------------- press shift
    "press_h_an": {"en": "{pressing_team_name} press {dir_t}", "hi": "{pressing_team_name} का प्रेस {dir_t}",
                   "ta": "{pressing_team_name} அழுத்தம் {dir_t}"},
    "press_b_an": {"en": "{press_rate_now} pressing actions per 100 {opponent_name} build-up passes, vs {press_rate_before} match baseline.",
                   "hi": "{opponent_name} के हर 100 बिल्ड-अप पास पर {press_rate_now} प्रेसिंग एक्शन, मैच औसत {press_rate_before}।",
                   "ta": "{opponent_name} அணியின் 100 பில்ட்-அப் பாஸ்களுக்கு {press_rate_now} அழுத்த முயற்சிகள்; போட்டி சராசரி {press_rate_before}."},
    "press_why_fading": {"en": "Expect {opponent_name} to get more time on the ball.",
                         "hi": "{opponent_name} को गेंद पर ज़्यादा समय मिलेगा।",
                         "ta": "{opponent_name} அணிக்கு பந்தில் அதிக நேரம் கிடைக்கும்."},
    "press_why_rising": {"en": "{opponent_name} will be rushed into mistakes.",
                         "hi": "{opponent_name} पर गलती करने का दबाव बढ़ेगा।",
                         "ta": "{opponent_name} தவறு செய்யும் அழுத்தம் கூடும்."},
    "press_h_ca_fading": {"en": "{pressing_team_name} are tiring", "hi": "{pressing_team_name} थक रहे हैं",
                          "ta": "{pressing_team_name} சோர்வடைகிறது"},
    "press_h_ca_rising": {"en": "{pressing_team_name} turn up the heat", "hi": "{pressing_team_name} ने दबाव बढ़ाया",
                          "ta": "{pressing_team_name} அழுத்தத்தைக் கூட்டியது"},
    "press_b_ca_fading": {"en": "They are chasing the ball far less than earlier, so {opponent_name} have more time.",
                          "hi": "वे पहले से काफ़ी कम दबाव डाल रहे हैं, इसलिए {opponent_name} के पास ज़्यादा समय है।",
                          "ta": "முன்பை விட மிகக் குறைவாக பந்தைத் துரத்துகிறார்கள்; {opponent_name} அணிக்கு அதிக நேரம்."},
    "press_b_ca_rising": {"en": "They are hunting the ball high up the pitch, and {opponent_name} are under pressure.",
                          "hi": "वे ऊपर जाकर गेंद छीनने में लगे हैं, {opponent_name} दबाव में है।",
                          "ta": "மைதானத்தின் மேலே பந்தை வேட்டையாடுகிறார்கள்; {opponent_name} அழுத்தத்தில்."},
    # ---------------------------------------------------------------- momentum
    "mom_h_an": {"en": "Momentum: {team_name}", "hi": "मोमेंटम: {team_name}", "ta": "உத்வேகம்: {team_name}"},
    "mom_b_an": {"en": "{threat_share_now}% of attacking threat over {threat_window_min} min, up from {threat_share_before}%. {possession_10min}% possession in the last {possession_window_min}.",
                 "hi": "पिछले {threat_window_min} मिनट में {threat_share_now}% अटैकिंग खतरा, पहले {threat_share_before}%। पिछले {possession_window_min} मिनट में {possession_10min}% पज़ेशन।",
                 "ta": "கடந்த {threat_window_min} நிமிடத்தில் {threat_share_now}% தாக்குதல் அச்சுறுத்தல், முன்பு {threat_share_before}%. கடந்த {possession_window_min} நிமிடத்தில் {possession_10min}% பந்து வசம்."},
    "mom_h_ca": {"en": "{team_name} on top", "hi": "{team_name} हावी", "ta": "{team_name} ஆதிக்கம்"},
    "mom_b_ca": {"en": "They are creating most of the danger right now.", "hi": "इस वक़्त ज़्यादातर खतरा वही पैदा कर रहे हैं।",
                 "ta": "இப்போது பெரும்பாலான ஆபத்தை அவர்களே உருவாக்குகிறார்கள்."},
    # ---------------------------------------------------------------- rhythm
    "rhy_h_an": {"en": "Rhythm: {from_t} to {to_t}", "hi": "लय: {from_t} से {to_t}", "ta": "ரிதம்: {from_t} முதல் {to_t}"},
    "rhy_b_an": {"en": "Possession changes {switches_per_min_now}/min (was {switches_per_min_before}); average move {avg_chain_now} passes (was {avg_chain_before}).",
                 "hi": "पज़ेशन बदलाव {switches_per_min_now}/मिनट (पहले {switches_per_min_before}); औसत मूव {avg_chain_now} पास (पहले {avg_chain_before})।",
                 "ta": "பந்து கைமாறல் {switches_per_min_now}/நிமிடம் (முன்பு {switches_per_min_before}); சராசரி நகர்வு {avg_chain_now} பாஸ் (முன்பு {avg_chain_before})."},
    "rhy_h_ca_chaos": {"en": "It's getting wild", "hi": "मैच बेकाबू हो रहा है", "ta": "ஆட்டம் சூடுபிடிக்கிறது"},
    "rhy_h_ca_control": {"en": "Calm, patient football", "hi": "शांत, धैर्य भरा खेल", "ta": "அமைதியான, பொறுமையான ஆட்டம்"},
    "rhy_h_ca_contested": {"en": "Evenly matched", "hi": "बराबरी की टक्कर", "ta": "சமமான போட்டி"},
    "rhy_b_ca_chaos": {"en": "The ball is changing hands far more often. Chances can come from nowhere.",
                       "hi": "गेंद बार-बार हाथ बदल रही है। मौके कहीं से भी आ सकते हैं।",
                       "ta": "பந்து அடிக்கடி கைமாறுகிறது. எங்கிருந்தும் வாய்ப்பு வரலாம்."},
    "rhy_b_ca_control": {"en": "Teams are keeping the ball longer and building slowly.",
                         "hi": "टीमें गेंद ज़्यादा देर रख रही हैं और धीरे-धीरे बिल्ड कर रही हैं।",
                         "ta": "அணிகள் பந்தை நீண்ட நேரம் வைத்து மெதுவாகக் கட்டமைக்கின்றன."},
    "rhy_b_ca_contested": {"en": "Neither side has control of the tempo.", "hi": "रफ़्तार पर किसी भी टीम का नियंत्रण नहीं।",
                           "ta": "எந்த அணிக்கும் ஆட்ட வேகத்தின் மீது கட்டுப்பாடு இல்லை."},
    # ---------------------------------------------------------------- card
    "card_h_an": {"en": "{card_t} card · {player}", "hi": "{card_t} कार्ड · {player}", "ta": "{card_t} அட்டை · {player}"},
    "card_b_an_tactical": {"en": "Tactical foul to stop a counter-attack. {team_name} cards: {team_cards}.",
                           "hi": "काउंटर-अटैक रोकने के लिए टैक्टिकल फ़ाउल। {team_name} के कुल कार्ड: {team_cards}।",
                           "ta": "எதிர்த்தாக்குதலைத் தடுக்க தந்திர ஃபவுல். {team_name} மொத்த அட்டைகள்: {team_cards}."},
    "card_b_an": {"en": "Booked for a foul. {team_name} cards: {team_cards}.",
                  "hi": "फ़ाउल के लिए बुक। {team_name} के कुल कार्ड: {team_cards}।",
                  "ta": "ஃபவுலுக்காக எச்சரிக்கை. {team_name} மொத்த அட்டைகள்: {team_cards}."},
    "card_h_ca": {"en": "{player} booked", "hi": "{player} को कार्ड", "ta": "{player} எச்சரிக்கப்பட்டார்"},
    "card_b_ca_tactical": {"en": "He took one for the team to stop a dangerous break.",
                           "hi": "खतरनाक काउंटर रोकने के लिए जानबूझकर फ़ाउल।",
                           "ta": "ஆபத்தான தாக்குதலைத் தடுக்க வேண்டுமென்றே ஃபவுல்."},
    "card_b_ca": {"en": "One more and he is in trouble.", "hi": "एक और कार्ड और मुश्किल।", "ta": "இன்னொரு அட்டை என்றால் சிக்கல்."},
    # ---------------------------------------------------------------- speed
    "spd_h_an": {"en": "{top_speed_kmh} km/h · {player}", "hi": "{top_speed_kmh} km/h · {player}", "ta": "{top_speed_kmh} km/h · {player}"},
    "spd_b_an": {"en": "Sprint of {sprint_distance_m} m, above the {threshold_kmh} km/h tag threshold.",
                 "hi": "{sprint_distance_m} मीटर की स्प्रिंट, {threshold_kmh} km/h सीमा से ऊपर।",
                 "ta": "{sprint_distance_m} மீ ஓட்டம், {threshold_kmh} km/h வரம்பைத் தாண்டி."},
    "spd_fastest": {"en": "Fastest in the match so far.", "hi": "मैच में अब तक सबसे तेज़।", "ta": "போட்டியில் இதுவரை அதிவேகம்."},
    "spd_h_ca": {"en": "Rapid! {player}", "hi": "बिजली जैसी रफ़्तार! {player}", "ta": "மின்னல் வேகம்! {player}"},
    "spd_b_ca": {"en": "Clocked {top_speed_kmh} km/h on a {sprint_distance_m} m run.",
                 "hi": "{sprint_distance_m} मीटर की दौड़ में {top_speed_kmh} km/h।",
                 "ta": "{sprint_distance_m} மீ ஓட்டத்தில் {top_speed_kmh} km/h."},
    # ---------------------------------------------------------------- rocket shot
    "rkt_h_an": {"en": "{shot_speed_kmh} km/h shot · {player}", "hi": "{shot_speed_kmh} km/h शॉट · {player}",
                 "ta": "{shot_speed_kmh} km/h ஷாட் · {player}"},
    "rkt_b_an": {"en": "From {distance_m} m, {outcome_t}. xG {xg}.", "hi": "{distance_m} मीटर से, {outcome_t}। xG {xg}।",
                 "ta": "{distance_m} மீ தூரத்திலிருந்து, {outcome_t}. xG {xg}."},
    "rkt_h_ca": {"en": "What a hit! {player}", "hi": "क्या शॉट! {player}", "ta": "என்ன ஒரு ஷாட்! {player}"},
    "rkt_b_ca": {"en": "{shot_speed_kmh} km/h from {distance_m} metres.", "hi": "{distance_m} मीटर से {shot_speed_kmh} km/h।",
                 "ta": "{distance_m} மீட்டரிலிருந்து {shot_speed_kmh} km/h."},
    # ---------------------------------------------------------------- line-breaking pass
    "lb_h_an": {"en": "Line-breaking pass · {player}", "hi": "लाइन तोड़ने वाला पास · {player}",
                "ta": "வரிசையை உடைக்கும் பாஸ் · {player}"},
    "lb_b_an": {"en": "{distance_m} m to {recipient}, {progressive_m} m forward, difficulty {difficulty}.",
                "hi": "{recipient} तक {distance_m} मीटर, {progressive_m} मीटर आगे, कठिनाई {difficulty}।",
                "ta": "{recipient} க்கு {distance_m} மீ, {progressive_m} மீ முன்னோக்கி, சிரமம் {difficulty}."},
    "lb_pressure": {"en": "Played under pressure.", "hi": "दबाव में खेला गया।", "ta": "அழுத்தத்தின் கீழ் கொடுக்கப்பட்டது."},
    "lb_h_ca": {"en": "Great pass! {player}", "hi": "शानदार पास! {player}", "ta": "அருமையான பாஸ்! {player}"},
    "lb_b_ca": {"en": "Found {recipient} {distance_m} metres away, cutting through the defence.",
                "hi": "{distance_m} मीटर दूर {recipient} को डिफ़ेंस के बीच से पास।",
                "ta": "{distance_m} மீட்டர் தொலைவில் {recipient} க்கு தடுப்பைப் பிளந்த பாஸ்."},
    # ---------------------------------------------------------------- distance
    "dist_h_an": {"en": "{distance_km} km · {player}", "hi": "{distance_km} km · {player}", "ta": "{distance_km} km · {player}"},
    "dist_b_an": {"en": "{rank_t} past {milestone_km} km. {sprints} sprints, {pressures} pressures.",
                  "hi": "{milestone_km} km पार करने वाले {rank_t} खिलाड़ी। {sprints} स्प्रिंट, {pressures} प्रेसिंग एक्शन।",
                  "ta": "{milestone_km} km கடந்த {rank_t} வீரர். {sprints} ஸ்பிரிண்ட், {pressures} அழுத்த முயற்சிகள்."},
    "rank_1": {"en": "First player", "hi": "पहले", "ta": "முதல்"},
    "rank_2": {"en": "Second player", "hi": "दूसरे", "ta": "இரண்டாவது"},
    "dist_h_ca": {"en": "Engine room: {player}", "hi": "{player} की अथक मेहनत", "ta": "ஓயாத உழைப்பு: {player}"},
    "dist_b_ca": {"en": "Already run {distance_km} km today.", "hi": "आज अब तक {distance_km} km दौड़ चुके।",
                  "ta": "இன்று ஏற்கனவே {distance_km} km ஓடியுள்ளார்."},
    # ---------------------------------------------------------------- substitution
    "sub_h_an": {"en": "Sub · {player_on} on, {player_off} off", "hi": "बदलाव · {player_on} अंदर, {player_off} बाहर",
                 "ta": "மாற்றம் · {player_on} உள்ளே, {player_off} வெளியே"},
    "sub_b_an": {"en": "{player_off} covered {off_distance_km} km with {off_sprints} sprints and {off_pressures} pressures.",
                 "hi": "{player_off}: {off_distance_km} km, {off_sprints} स्प्रिंट, {off_pressures} प्रेसिंग एक्शन।",
                 "ta": "{player_off}: {off_distance_km} km, {off_sprints} ஸ்பிரிண்ட், {off_pressures} அழுத்த முயற்சிகள்."},
    "sub_h_ca": {"en": "Change for {team_name}", "hi": "{team_name} में बदलाव", "ta": "{team_name} அணியில் மாற்றம்"},
    "sub_b_ca": {"en": "Fresh legs: {player_on} replaces {player_off}.", "hi": "ताज़ा पैर: {player_off} की जगह {player_on}।",
                 "ta": "புதிய கால்கள்: {player_off} பதிலாக {player_on}."},
    # ---------------------------------------------------------------- pass milestone
    "pm_h_an": {"en": "{passes_completed} completed passes · {player}", "hi": "{passes_completed} सफल पास · {player}",
                "ta": "{passes_completed} வெற்றிகரமான பாஸ்கள் · {player}"},
    "pm_b_an": {"en": "First to {passes_completed}, at {pass_accuracy_pct}% accuracy.",
                "hi": "{passes_completed} तक पहुँचने वाले पहले खिलाड़ी, {pass_accuracy_pct}% सटीकता।",
                "ta": "{passes_completed} எட்டிய முதல் வீரர், {pass_accuracy_pct}% துல்லியம்."},
    "pm_h_ca": {"en": "Running the show: {player}", "hi": "खेल पर पकड़: {player}", "ta": "ஆட்டத்தை இயக்குபவர்: {player}"},
    "pm_b_ca": {"en": "{passes_completed} passes completed already.", "hi": "अब तक {passes_completed} सफल पास।",
                "ta": "ஏற்கனவே {passes_completed} வெற்றிகரமான பாஸ்கள்."},
    # ---------------------------------------------------------------- recaps
    "ht_h": {"en": "Half-time · {home_name} {score_home}-{score_away} {away_name}",
             "hi": "हाफ़-टाइम · {home_name} {score_home}-{score_away} {away_name}",
             "ta": "இடைவேளை · {home_name} {score_home}-{score_away} {away_name}"},
    "ft_h": {"en": "Full-time · {home_name} {score_home}-{score_away} {away_name}",
             "hi": "फ़ुल-टाइम · {home_name} {score_home}-{score_away} {away_name}",
             "ta": "ஆட்ட முடிவு · {home_name} {score_home}-{score_away} {away_name}"},
    "recap_b_an": {"en": "Possession {possession_home}-{possession_away}% · Shots {shots_home}-{shots_away} · xG {xg_home}-{xg_away} · PPDA {ppda_home}-{ppda_away}. Fastest: {fastest_player} {fastest_kmh} km/h.",
                   "hi": "पज़ेशन {possession_home}-{possession_away}% · शॉट {shots_home}-{shots_away} · xG {xg_home}-{xg_away} · PPDA {ppda_home}-{ppda_away}। सबसे तेज़: {fastest_player} {fastest_kmh} km/h।",
                   "ta": "பந்து வசம் {possession_home}-{possession_away}% · ஷாட் {shots_home}-{shots_away} · xG {xg_home}-{xg_away} · PPDA {ppda_home}-{ppda_away}. அதிவேகம்: {fastest_player} {fastest_kmh} km/h."},
    "recap_lead_ht": {"en": "{leader} lead at the break.", "hi": "ब्रेक पर {leader} आगे।", "ta": "இடைவேளையில் {leader} முன்னிலை."},
    "recap_lead_ft": {"en": "{leader} win it.", "hi": "{leader} की जीत।", "ta": "{leader} வெற்றி."},
    "recap_level": {"en": "All square.", "hi": "मुक़ाबला बराबर।", "ta": "சமநிலை."},
    "recap_goals": {"en": "Goals: {goals}.", "hi": "गोल: {goals}।", "ta": "கோல்கள்: {goals}."},
    "recap_work": {"en": "Hardest worker: {most_distance_player}, {most_distance_km} km.",
                   "hi": "सबसे ज़्यादा दौड़े: {most_distance_player}, {most_distance_km} km।",
                   "ta": "அதிகம் ஓடியவர்: {most_distance_player}, {most_distance_km} km."},
}


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _f(key: str, lang: str, values: dict) -> str:
    return P[key][lang].format_map(_Safe(values))


def _num(v):
    if isinstance(v, float) and v.is_integer() and abs(v) >= 10:
        return int(v)
    return v


def sentiment(moment: dict, club: str | None) -> str | None:
    """How a moment lands for a fan of `club`: good, bad, relief, close, or None (neutral)."""
    if not club:
        return None
    t, team, e = moment["type"], moment.get("team"), moment["evidence"]
    if team is None:
        return None
    mine = team == club
    if t == "goal":
        return "good" if mine else "bad"
    if t == "big_chance":
        return "close" if mine else "relief"
    if t == "press_shift":
        good = (e["direction"] == "rising") == mine
        return "good" if good else "bad"
    if t == "momentum_swing":
        return "good" if mine else "bad"
    if t == "card":
        return "bad" if mine else None
    return None


def render(moment: dict, mode: str = "analyst", lang: str = "en", club: str | None = None,
           club_name: str | None = None) -> dict:
    """Render one moment for one profile. Returns {"headline", "body"}."""
    if lang not in LANGS:
        lang = "en"
    e = {k: _num(v) for k, v in moment["evidence"].items()}
    t = moment["type"]
    an = mode in ("analyst", "player")
    h, b = "", []

    if t == "goal":
        h = _f("goal_h_an" if an else "goal_h_ca", lang, e)
        b.append(_f("goal_b_an" if an else "goal_b_ca", lang, e))
        tags = moment["evidence"].get("why_tags", [])
        sfx = "_an" if an else "_ca"
        if "counterpress_regain" in tags and "regain_player" in e:
            b.append(_f("why_counter" + sfx, lang, e))
        elif "low_xg_strike" in tags:
            b.append(_f("why_lowxg" + sfx, lang, e))
        elif "patient_buildup" in tags:
            b.append(_f("why_patient" + sfx, lang, e))
        if e.get("related_type") == "press_shift" and "related_press_rate_now" in e:
            b.append(_f("rel_press" + sfx, lang, e))
        elif e.get("related_type") == "momentum_swing" and "related_threat_share_now" in e:
            b.append(_f("rel_mom" + sfx, lang, e))
    elif t == "big_chance":
        e["outcome_t"] = P.get(e["outcome"], P["saved"])[lang]
        h = _f("big_h_an" if an else "big_h_ca", lang, e)
        b.append(_f("big_b_an" if an else "big_b_ca", lang, e))
    elif t == "press_shift":
        d = e["direction"]
        e["dir_t"] = P[d][lang]
        if an:
            h = _f("press_h_an", lang, e)
            b += [_f("press_b_an", lang, e), _f("press_why_" + d, lang, e)]
        else:
            h = _f("press_h_ca_" + d, lang, e)
            b.append(_f("press_b_ca_" + d, lang, e))
    elif t == "momentum_swing":
        h = _f("mom_h_an" if an else "mom_h_ca", lang, e)
        b.append(_f("mom_b_an" if an else "mom_b_ca", lang, e))
    elif t == "rhythm_shift":
        e["from_t"], e["to_t"] = P[e["from_label"]][lang], P[e["to_label"]][lang]
        if an:
            h, b = _f("rhy_h_an", lang, e), [_f("rhy_b_an", lang, e)]
        else:
            h, b = _f("rhy_h_ca_" + e["to_label"], lang, e), [_f("rhy_b_ca_" + e["to_label"], lang, e)]
    elif t == "card":
        e["card_t"] = P[e["card"]][lang]
        tactical = e.get("reason") == "tactical foul"
        if an:
            h, b = _f("card_h_an", lang, e), [_f("card_b_an_tactical" if tactical else "card_b_an", lang, e)]
        else:
            h, b = _f("card_h_ca", lang, e), [_f("card_b_ca_tactical" if tactical else "card_b_ca", lang, e)]
    elif t == "top_speed":
        h = _f("spd_h_an" if an else "spd_h_ca", lang, e)
        b.append(_f("spd_b_an" if an else "spd_b_ca", lang, e))
        if an and e.get("match_fastest"):
            b.append(_f("spd_fastest", lang, e))
    elif t == "rocket_shot":
        e["outcome_t"] = P.get(e["outcome"], P["saved"])[lang]
        h = _f("rkt_h_an" if an else "rkt_h_ca", lang, e)
        b.append(_f("rkt_b_an" if an else "rkt_b_ca", lang, e))
    elif t == "line_breaker":
        h = _f("lb_h_an" if an else "lb_h_ca", lang, e)
        b.append(_f("lb_b_an" if an else "lb_b_ca", lang, e))
        if an and e.get("under_pressure"):
            b.append(_f("lb_pressure", lang, e))
    elif t == "distance_milestone":
        e["rank_t"] = P["rank_1" if e.get("rank") == 1 else "rank_2"][lang]
        h = _f("dist_h_an" if an else "dist_h_ca", lang, e)
        b.append(_f("dist_b_an" if an else "dist_b_ca", lang, e))
    elif t == "substitution":
        h = _f("sub_h_an" if an else "sub_h_ca", lang, e)
        b.append(_f("sub_b_an" if an else "sub_b_ca", lang, e))
    elif t == "pass_milestone":
        h = _f("pm_h_an" if an else "pm_h_ca", lang, e)
        b.append(_f("pm_b_an" if an else "pm_b_ca", lang, e))
    elif t in ("half_time", "full_time"):
        h = _f("ht_h" if t == "half_time" else "ft_h", lang, e)
        if an:
            b.append(_f("recap_b_an", lang, e))
        else:
            sh, sa = e["score_home"], e["score_away"]
            if sh == sa:
                b.append(_f("recap_level", lang, e))
            else:
                leader = e["home_name"] if sh > sa else e["away_name"]
                b.append(_f("recap_lead_ht" if t == "half_time" else "recap_lead_ft", lang, {"leader": leader}))
            goals = [f"{g['player'].split(' ')[-1]} {g['minute']}" for g in moment["evidence"].get("goals", [])]
            if goals:
                b.append(_f("recap_goals", lang, {"goals": ", ".join(goals)}))
            b.append(_f("recap_work", lang, e))
    else:
        h, b = moment["type"], []

    s = sentiment(moment, club)
    if s and mode == "casual" and club_name:
        b.insert(0, _f("persp_" + s, lang, {"club": club_name}))
    return {"headline": h, "body": " ".join(b)}
