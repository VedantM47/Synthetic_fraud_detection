"""Web backend for the synthetic identity fraud detection project.

The backend wires the research pipeline in ``data_generation`` and ``src``
into a service: upload -> identity graph -> features -> model training ->
scoring and explanations -> fraud-ring detection -> SQLite -> frontend.
"""
