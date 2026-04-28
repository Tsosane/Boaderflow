DROP VIEW IF EXISTS container_current_state_v;

CREATE VIEW container_current_state_v AS
WITH latest_milestone AS (
    SELECT
        m.*,
        ROW_NUMBER() OVER (
            PARTITION BY m.container_id
            ORDER BY m.milestone_time DESC, m.created_at DESC
        ) AS rn
    FROM milestone AS m
),
latest_handover AS (
    SELECT
        h.*,
        ROW_NUMBER() OVER (
            PARTITION BY h.container_id
            ORDER BY h.handover_time DESC, h.created_at DESC
        ) AS rn
    FROM handover AS h
),
active_assignment AS (
    SELECT
        tc.container_id,
        tc.trip_id
    FROM trip_container AS tc
    WHERE tc.active_assignment IS TRUE
)
SELECT
    c.id AS container_id,
    c.consignment_id,
    c.container_no,
    cons.reference_no AS consignment_ref,
    COALESCE(lm.milestone_type, 'REGISTERED') AS current_status,
    current_site.code AS current_site_code,
    current_site.name AS current_site_name,
    lm.milestone_type AS latest_milestone_type,
    lm.milestone_time AS latest_milestone_time,
    lh.handover_time AS last_handover_time,
    aa.trip_id,
    t.status AS trip_status
FROM container AS c
JOIN consignment AS cons ON cons.id = c.consignment_id
LEFT JOIN latest_milestone AS lm ON lm.container_id = c.id AND lm.rn = 1
LEFT JOIN latest_handover AS lh ON lh.container_id = c.id AND lh.rn = 1
LEFT JOIN active_assignment AS aa ON aa.container_id = c.id
LEFT JOIN trip AS t ON t.id = aa.trip_id
LEFT JOIN site AS current_site ON current_site.id = COALESCE(lh.to_site_id, lm.site_id, cons.origin_site_id);

DROP PUBLICATION IF EXISTS pub_depot_master;
CREATE PUBLICATION pub_depot_master
    FOR TABLE
        site,
        app_user WHERE (origin_site_code = 'DEPOT-MSU'),
        client WHERE (origin_site_code = 'DEPOT-MSU'),
        vehicle WHERE (origin_site_code = 'DEPOT-MSU'),
        driver WHERE (origin_site_code = 'DEPOT-MSU'),
        consignment WHERE (origin_site_code = 'DEPOT-MSU'),
        container WHERE (origin_site_code = 'DEPOT-MSU'),
        trip WHERE (origin_site_code = 'DEPOT-MSU'),
        trip_container WHERE (origin_site_code = 'DEPOT-MSU'),
        event_log WHERE (origin_site_code = 'DEPOT-MSU');

DROP PUBLICATION IF EXISTS pub_border_events;
CREATE PUBLICATION pub_border_events
    FOR TABLE
        milestone WHERE (origin_site_code = 'BORDER-MB'),
        handover WHERE (origin_site_code = 'BORDER-MB'),
        incident WHERE (origin_site_code = 'BORDER-MB'),
        event_log WHERE (origin_site_code = 'BORDER-MB');

DROP PUBLICATION IF EXISTS pub_port_events;
CREATE PUBLICATION pub_port_events
    FOR TABLE
        milestone WHERE (origin_site_code = 'PORT-DBN'),
        handover WHERE (origin_site_code = 'PORT-DBN'),
        incident WHERE (origin_site_code = 'PORT-DBN'),
        event_log WHERE (origin_site_code = 'PORT-DBN');

DROP PUBLICATION IF EXISTS pub_hub_events;
CREATE PUBLICATION pub_hub_events
    FOR TABLE
        milestone WHERE (origin_site_code = 'HUB-JHB'),
        handover WHERE (origin_site_code = 'HUB-JHB'),
        incident WHERE (origin_site_code = 'HUB-JHB'),
        event_log WHERE (origin_site_code = 'HUB-JHB');

-- Subscriptions are created repeatably by the runtime CLI using the replication topology:
-- python -m app.cli setup-replication --topology infra/replication_topology.json --reset
