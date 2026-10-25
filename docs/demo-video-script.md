# Demo video script (target 1:50, hard limit under 2:00)

Record the deployed app, not localhost, so the Azure URL is visible. Use the seed-21 match. Set replay speed to 30x and use the jump buttons on `/replay`, or let the live viewer run. No league or club marks, no copyrighted music (silence or royalty-free).

| Time | Screen | Voice-over |
|---|---|---|
| 0:00-0:12 | Viewer, match running | "Broadcast graphics tell you what happened. They rarely tell you why, and everyone gets the same one. Match Insights Studio fixes that, live, on Azure." |
| 0:12-0:35 | 19' goal lower third, click "Why?" | "Synthetic events stream in. The interpreter turns them into stats and moments. Here a Foundry agent explains the goal: a 13-pass move. The Why drawer shows the exact evidence it was allowed to use." |
| 0:35-0:58 | 58' press-fade stat card, then the 62' goal | "At 58 minutes the engine spots Northvale's press fading. Four minutes later Saltmere score from 31 metres at 118 km/h with 0.01 xG, and the overlay links the goal to that press." |
| 0:58-1:15 | Switch to Casual fan, Tamil, club = Saltmere; then Player focus | "Same moment, different viewer. A casual Saltmere fan watching in Tamil gets plain words and their club's point of view. Player focus follows one player all match." |
| 1:15-1:35 | Producer desk: reject one, edit and air one, audit trail, verifier count | "Nothing airs unchecked. A code verifier rejects any number or name not in the evidence and sends the draft back. A producer can approve, edit or reject, and every decision is logged." |
| 1:35-1:50 | Architecture diagram from the README, then `/api/health` showing foundry:<model> | "Narrator, Personalizer and Recapper agents on Microsoft Foundry and Agent Framework, running on Azure Container Apps with a managed identity. Synthetic data, real broadcast workflow." |

Screenshots to upload to Project Images/Video: the 62' goal overlay (analyst), the same moment in casual Tamil, the Why drawer, the producer desk with the audit trail, the architecture diagram.
