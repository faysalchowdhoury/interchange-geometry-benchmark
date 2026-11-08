The diverging diamond won my interchange screening at today's demand. It also had the higher chance of failing by 2045.

I built a Cap-X-style screening harness in Python that routes the same origin-destination demand through a conventional diamond, a DDI and a turbo-roundabout dumbbell (critical lane volume for the signals, HCM 7 entry capacity for the roundabouts), and sweeps thousands of demand futures.

At balanced demand (1,000 vph through, 600 vph ramps):
🔹 DDI: 32.9 s/veh, LOS C, 38% less delay than the diamond
🔹 Diamond: 53.0 s/veh, LOS D, but 28% capacity reserve vs the DDI's 23%
🔹 Monte Carlo to 2045 (±10% counts, 1.5%/yr growth): P(v/c > 1) is 61% for the diamond vs 69% for the DDI

What the sweep shows:
1️⃣ The DDI's strength is left turns. With 70% of ramp traffic turning left, the diamond fails (v/c 1.27) and the DDI holds (0.96).
2️⃣ Its weakness is through traffic: both directions share the crossover cycle. With 1,500 vph through per direction, the DDI fails (v/c 1.04) while the diamond is fine (0.77).
3️⃣ The turbo dumbbell is best when ramps are light (under ~400-500 vph). Off-ramp lefts have to yield to all circulating arterial traffic.
4️⃣ Report reserve and risk, not just base-year delay. The ranking flips depending on which you ask.

Engineering-software side: everything is NumPy broadcasting, with no loops over scenarios. That's 1.1 million design evaluations per second, vectorised bisection for capacity reserve, and a FastAPI endpoint that ranks three designs in under a millisecond. 10 pytest cases check hand-calculated CLVs and the HCM formulas.

Caveat: planning-level screening (no spillback or weaving), and turbo capacity uses HCM multilane coefficients with lane-separated conflicts.

Repo: [link]

Interchange folks: what demand pattern pushed you away from a DDI on a real project?

#TrafficEngineering #InterchangeDesign #DDI #Roundabouts #HCM #TransportationPlanning #Python #DataScience
