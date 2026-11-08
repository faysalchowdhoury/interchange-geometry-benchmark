"""interchange-geometry-benchmark.

Planning-level (FHWA Cap-X style) screening of service interchanges: conventional diamond,
diverging diamond (DDI) and turbo-roundabout dumbbell. The same origin-destination demand is
routed through each geometry, analysed with critical lane volumes (signals) or HCM 7 entry
capacity (roundabouts), and swept over thousands of demand scenarios with vectorised NumPy.
"""

__version__ = "1.0.0"
