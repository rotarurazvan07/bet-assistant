// Shared recharts test stub (final-gate fix, cycle 13).
//
// WHY THIS EXISTS: vitest runs with pool 'threads' + isolate:false +
// fileParallelism:false — ONE worker, ONE module registry, files in sequence.
// A vi.mock('recharts') factory registered in only ONE test file is
// order-dependent: if a file that imports REAL recharts runs first (e.g. the
// Analytics PAGE test), the real module is cached and a later file's mock
// registration comes too late — its capture probe never fires (the 5-test
// intermittent failure the final gate caught). The order-robust fix: EVERY
// file that renders recharts registers the IDENTICAL factory from this
// helper, so whichever file runs first defines recharts for the whole
// worker — always this stub.
//
// Registration (in EACH consuming test file, TOP LEVEL — vitest hoists
// top-level vi.mock calls above imports; a function-wrapped call registers
// too late, so use this exact line verbatim):
//   vi.mock('recharts', async () => (await import('../../test/recharts-stub')).rechartsStub);
//   import { radarChartMock } from '../../test/recharts-stub'; // only where asserted
//
// radarChartMock is the capture probe for RadarChart data-prop assertions.
// Clear it in beforeEach at each site that asserts on it (restoreMocks in
// vitest.config also clears it after every test).

import { vi } from 'vitest';

export const radarChartMock = vi.fn();

/** Every recharts export the app imports, stubbed as a harmless div.
 * RadarChart is the capture probe (asserts radarData shape). */
export const rechartsStub = {
    RadarChart: (props: unknown) => { radarChartMock(props); return null; },
    PolarGrid: () => null,
    PolarAngleAxis: () => null,
    PolarRadiusAxis: () => null,
    Radar: () => null,
    ResponsiveContainer: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    LineChart: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    BarChart: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    AreaChart: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ComposedChart: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ScatterChart: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    PieChart: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    Line: () => null,
    Bar: () => null,
    Area: () => null,
    Scatter: () => null,
    Pie: () => null,
    Sector: () => null,
    Cell: () => null,
    XAxis: () => null,
    YAxis: () => null,
    ZAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
    ReferenceLine: () => null,
    ReferenceArea: () => null,
    ReferenceDot: () => null,
    Brush: () => null,
    ErrorBar: () => null,
    Text: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    Label: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    LabelList: () => null,
    Surface: () => null,
    Curve: () => null,
    Cross: () => null,
    Dot: () => null,
    Polygon: () => null,
    Rectangle: () => null,
    Symbols: () => null,
    Trapezoid: () => null,
};

// NOTE: this file must contain NO vi.mock call of its own — the registration
// line lives at the TOP LEVEL of each consuming test file (vitest hoists it
// there); a mock defined inside this module's function scope trips the
// hoisting analyzer at transform time (Gate-1 lesson).
