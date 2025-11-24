--
-- PostgreSQL database dump
--

-- Dumped from database version 15.14
-- Dumped by pg_dump version 16.4

-- Started on 2025-11-16 16:43:17

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 9 (class 2615 OID 23801)
-- Name: sch_msoft; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA sch_msoft;


ALTER SCHEMA sch_msoft OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 580 (class 1259 OID 23803)
-- Name: tbl_zone_change_events; Type: TABLE; Schema: sch_msoft; Owner: postgres
--

CREATE TABLE sch_msoft.tbl_zone_change_events (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    message text,
    service_origin character varying(100),
    mqtt_topic character varying(255),
    user_id character varying(100),
    zone_previous smallint,
    zone_new smallint,
    bpm numeric(6,2)
);


ALTER TABLE sch_msoft.tbl_zone_change_events OWNER TO postgres;

--
-- TOC entry 579 (class 1259 OID 23802)
-- Name: tbl_zone_change_events_id_seq; Type: SEQUENCE; Schema: sch_msoft; Owner: postgres
--

CREATE SEQUENCE sch_msoft.tbl_zone_change_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE sch_msoft.tbl_zone_change_events_id_seq OWNER TO postgres;

--
-- TOC entry 5164 (class 0 OID 0)
-- Dependencies: 579
-- Name: tbl_zone_change_events_id_seq; Type: SEQUENCE OWNED BY; Schema: sch_msoft; Owner: postgres
--

ALTER SEQUENCE sch_msoft.tbl_zone_change_events_id_seq OWNED BY sch_msoft.tbl_zone_change_events.id;


--
-- TOC entry 5011 (class 2604 OID 23806)
-- Name: tbl_zone_change_events id; Type: DEFAULT; Schema: sch_msoft; Owner: postgres
--

ALTER TABLE ONLY sch_msoft.tbl_zone_change_events ALTER COLUMN id SET DEFAULT nextval('sch_msoft.tbl_zone_change_events_id_seq'::regclass);


--
-- TOC entry 5158 (class 0 OID 23803)
-- Dependencies: 580
-- Data for Name: tbl_zone_change_events; Type: TABLE DATA; Schema: sch_msoft; Owner: postgres
--

COPY sch_msoft.tbl_zone_change_events (id, created_at, message, service_origin, mqtt_topic, user_id, zone_previous, zone_new, bpm) FROM stdin;
\.


--
-- TOC entry 5165 (class 0 OID 0)
-- Dependencies: 579
-- Name: tbl_zone_change_events_id_seq; Type: SEQUENCE SET; Schema: sch_msoft; Owner: postgres
--

SELECT pg_catalog.setval('sch_msoft.tbl_zone_change_events_id_seq', 1, false);


--
-- TOC entry 5014 (class 2606 OID 23811)
-- Name: tbl_zone_change_events tbl_zone_change_events_pkey; Type: CONSTRAINT; Schema: sch_msoft; Owner: postgres
--

ALTER TABLE ONLY sch_msoft.tbl_zone_change_events
    ADD CONSTRAINT tbl_zone_change_events_pkey PRIMARY KEY (id);


-- Completed on 2025-11-16 16:43:23

--
-- PostgreSQL database dump complete
--

