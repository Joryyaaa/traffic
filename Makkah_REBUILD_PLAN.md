# Makkah Ibrahim Al Khalil — clean rebuild plan

This branch intentionally starts from the validated/optimized Abha Ibex branch and rebuilds Makkah from scratch.

Order of work before any production Ibex submission:
1. Freeze one OSM snapshot for the Ibrahim Al Khalil hotspot.
2. Validate reviewed OSM ways/nodes, connectivity, one-way metadata, and road classes.
3. Save/render B0 from that snapshot.
4. Derive S1/S2/S3 only from B0; never refetch a second road network for scenarios.
5. Validate every scenario target against B0 and reject unsupported cases instead of substituting arbitrary roads.
6. Validate Madina configs against the repository backend and data columns.
7. Run smoke/timing tests on the frozen snapshot.
8. Optimize only repeated computation/parallel execution; do not alter scenario meaning.
9. Only then provide the final Ibex submission scripts and expected output locations.

No production Ibex run should depend on live Overpass access.
