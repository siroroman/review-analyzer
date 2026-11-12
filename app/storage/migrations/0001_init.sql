-- Companies, Places and their membership. A Place can belong to several Companies.
CREATE TABLE companies (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    places_key  text NOT NULL UNIQUE,
    name        text NOT NULL,
    industry    text NOT NULL
);

CREATE TABLE places (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source       text NOT NULL,
    external_id  text NOT NULL,
    name         text NOT NULL,
    address      text NOT NULL,
    UNIQUE (source, external_id)
);

CREATE TABLE company_places (
    company_id  bigint NOT NULL REFERENCES companies (id),
    place_id    bigint NOT NULL REFERENCES places (id),
    position    integer NOT NULL,
    PRIMARY KEY (company_id, place_id)
);
CREATE INDEX company_places_place ON company_places (place_id);

-- A Review holds no reviewer data: no name, no profile, no author id (GDPR). Do not add such a column.
CREATE TABLE reviews (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    place_id        bigint NOT NULL REFERENCES places (id),
    source          text NOT NULL,
    external_id     text NOT NULL,
    rating          smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
    text            text NOT NULL,
    published_on    date NOT NULL,
    date_precision  text NOT NULL,
    language        text,
    text_hash       text NOT NULL,
    flagged         boolean NOT NULL,
    UNIQUE (source, external_id)
);
CREATE INDEX reviews_place ON reviews (place_id, published_on, external_id);

-- A Taxonomy version never changes: the triggers below refuse UPDATE and DELETE.
CREATE TABLE taxonomies (
    industry  text NOT NULL,
    version   integer NOT NULL CHECK (version >= 1),
    PRIMARY KEY (industry, version)
);

CREATE TABLE taxonomy_topics (
    industry     text NOT NULL,
    version      integer NOT NULL,
    position     integer NOT NULL,
    key          text NOT NULL,
    name         text NOT NULL,
    description  text NOT NULL,
    PRIMARY KEY (industry, version, key),
    FOREIGN KEY (industry, version) REFERENCES taxonomies (industry, version)
);

CREATE FUNCTION refuse_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'a % row is immutable', TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation';
END
$$;

CREATE TRIGGER taxonomies_immutable BEFORE UPDATE OR DELETE ON taxonomies
    FOR EACH ROW EXECUTE FUNCTION refuse_change();
CREATE TRIGGER taxonomy_topics_immutable BEFORE UPDATE OR DELETE ON taxonomy_topics
    FOR EACH ROW EXECUTE FUNCTION refuse_change();

CREATE TABLE review_topics (
    review_id   bigint NOT NULL REFERENCES reviews (id),
    industry    text NOT NULL,
    version     integer NOT NULL,
    topic_key   text NOT NULL,
    sentiment   text NOT NULL,
    confidence  double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (review_id, industry, version, topic_key),
    FOREIGN KEY (industry, version) REFERENCES taxonomies (industry, version)
);

CREATE SEQUENCE run_ids;

CREATE TABLE runs (
    id           text PRIMARY KEY DEFAULT nextval('run_ids')::text,
    company_id   bigint NOT NULL REFERENCES companies (id),
    status       text NOT NULL,
    budget_cap   numeric NOT NULL,
    created_at   timestamptz NOT NULL,
    finished_at  timestamptz
);
CREATE INDEX runs_company ON runs (company_id, finished_at);

CREATE TABLE insights (
    seq           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        text NOT NULL REFERENCES runs (id),
    type          text NOT NULL,
    period_start  date NOT NULL,
    period_end    date NOT NULL,
    text          text NOT NULL,
    review_ids    text[] NOT NULL
);
CREATE INDEX insights_run ON insights (run_id, seq);

CREATE TABLE trend_points (
    seq             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          text NOT NULL REFERENCES runs (id),
    source          text NOT NULL,
    period_start    date NOT NULL,
    average_rating  double precision NOT NULL,
    count           integer NOT NULL,
    sentiment       double precision NOT NULL
);
CREATE INDEX trend_points_run ON trend_points (run_id, seq);

-- The Call log: never a request or response body (untrusted text, GDPR).
CREATE TABLE service_calls (
    seq         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service     text NOT NULL,
    operation   text NOT NULL,
    run_id      text NOT NULL,
    status      text NOT NULL,
    cost        numeric NOT NULL,
    unit        text NOT NULL,
    units       bigint NOT NULL,
    latency     interval NOT NULL,
    error_kind  text,
    at          timestamptz NOT NULL
);
CREATE INDEX service_calls_at ON service_calls (at, seq);
CREATE INDEX service_calls_run ON service_calls (run_id);
CREATE INDEX service_calls_service ON service_calls (service);
