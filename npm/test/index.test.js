const assert = require('node:assert/strict');
const { test } = require('node:test');
const { TaxPreFlight } = require('../dist/index.js');

const overThresholdIntent = (claim) => ({
    state: 'NY',
    sales_data: { amount: 600000, transactions: 0 },
    ...(claim === undefined ? {} : { claimed_collects_tax: claim }),
});

test('blocks an over-threshold sale with a structured no-tax claim', () => {
    const result = TaxPreFlight.audit(overThresholdIntent(false));

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /Nexus threshold exceeded in NY/);
});

test('allows an over-threshold sale with a structured tax-collection claim', () => {
    const result = TaxPreFlight.audit(overThresholdIntent(true));

    assert.equal(result.allowed, true);
    assert.deepEqual(result.blocks, []);
});

test('keeps the legacy no-tax claim working for over-threshold sales', () => {
    const result = TaxPreFlight.audit({
        ...overThresholdIntent(),
        tax_decision: 'no_tax',
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /Nexus threshold exceeded in NY/);
});

test('blocks an over-threshold sale without a tax claim', () => {
    const result = TaxPreFlight.audit(overThresholdIntent());

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /Provide claimed_collects_tax/);
});

test('blocks an over-threshold sale with a non-boolean tax claim', () => {
    const result = TaxPreFlight.audit(overThresholdIntent('false'));

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /Provide claimed_collects_tax/);
});

test('does not let the legacy fallback mask an invalid structured claim', () => {
    const result = TaxPreFlight.audit({
        ...overThresholdIntent('false'),
        tax_decision: 'no_tax',
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /Provide claimed_collects_tax/);
});

test('allows a below-threshold sale with a structured no-tax claim', () => {
    const result = TaxPreFlight.audit({
        ...overThresholdIntent(false),
        sales_data: { amount: 100, transactions: 0 },
    });

    assert.equal(result.allowed, true);
    assert.deepEqual(result.blocks, []);
});

test('does not treat a zero transaction threshold as crossed', () => {
    const result = TaxPreFlight.audit({
        state: 'CA',
        sales_data: { amount: 100, transactions: 0 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, true);
    assert.deepEqual(result.blocks, []);
});

test('blocks an unknown state instead of treating it as verified', () => {
    const result = TaxPreFlight.audit({
        state: 'WA',
        sales_data: { amount: 100, transactions: 0 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /not in configured nexus threshold table/);
});

test('blocks a NaN sales amount instead of reading it as below-threshold', () => {
    const result = TaxPreFlight.audit({
        state: 'CA',
        sales_data: { amount: NaN, transactions: 0 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /ytd_sales must be a finite numeric value/);
});

test('blocks NaN transactions on a transaction-threshold state', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        sales_data: { amount: 100, transactions: NaN },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /transactions must be a finite numeric value/);
});

test('blocks an infinite sales amount', () => {
    const result = TaxPreFlight.audit({
        state: 'CA',
        sales_data: { amount: Infinity, transactions: 0 },
        claimed_collects_tax: true,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /ytd_sales must be a finite numeric value/);
});

test('blocks a non-numeric sales amount', () => {
    const result = TaxPreFlight.audit({
        state: 'CA',
        sales_data: { amount: '100000', transactions: 0 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /ytd_sales must be a finite numeric value/);
});

test('blocks a negative sales amount instead of reading it as below-threshold', () => {
    const result = TaxPreFlight.audit({
        state: 'CA',
        sales_data: { amount: -5000, transactions: 0 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /ytd_sales must be a non-negative numeric value/);
});

test('blocks negative transactions', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        sales_data: { amount: 100, transactions: -3 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /transactions must be a non-negative numeric value/);
});

test('blocks a non-string state instead of crashing', () => {
    const result = TaxPreFlight.audit({
        state: 42,
        sales_data: { amount: 100, transactions: 0 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /state must be a string/);
});

test('does not let an empty-string state skip nexus validation', () => {
    const result = TaxPreFlight.audit({
        state: '',
        sales_data: { amount: 600000, transactions: 0 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /not in configured nexus threshold table/);
});

test('does not let a null state skip nexus validation', () => {
    const result = TaxPreFlight.audit({
        state: null,
        sales_data: { amount: 600000, transactions: 0 },
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /state must be a string/);
});

// Falsy-but-present sales_data must fail closed, not skip validation.
test('blocks null sales_data instead of skipping nexus validation', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        sales_data: null,
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /sales_data must be an object/);
});

test('blocks false sales_data instead of skipping nexus validation', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        sales_data: false,
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /sales_data must be an object/);
});

test('blocks zero sales_data instead of skipping nexus validation', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        sales_data: 0,
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /sales_data must be an object/);
});

test('blocks empty-string sales_data instead of skipping nexus validation', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        sales_data: '',
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /sales_data must be an object/);
});

test('blocks array sales_data instead of skipping nexus validation', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        sales_data: [{ amount: 600000, transactions: 0 }],
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /sales_data must be an object/);
});

test('blocks explicit undefined sales_data instead of skipping nexus validation', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        sales_data: undefined,
        tax_decision: 'no_tax',
    });

    assert.equal(result.allowed, false);
    assert.match(result.blocks[0], /sales_data must be an object/);
});

test('skips nexus when sales_data is not provided', () => {
    const result = TaxPreFlight.audit({
        state: 'NY',
        claimed_collects_tax: false,
    });

    assert.equal(result.allowed, true);
    assert.deepEqual(result.blocks, []);
});
