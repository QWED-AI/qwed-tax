export enum WorkerType {
    EMPLOYEE = "W2",
    CONTRACTOR = "1099"
}

export class ClassificationGuard {
    /**
     * Deterministic IRS Common Law Test.
     */
    static verifyWorkerStatus(behavioralControl: boolean, financialControl: boolean, relationshipPermanence: boolean): WorkerType {
        if (behavioralControl && financialControl) {
            return WorkerType.EMPLOYEE;
        }
        if (relationshipPermanence && behavioralControl) {
            return WorkerType.EMPLOYEE;
        }
        return WorkerType.CONTRACTOR;
    }
}

export class NexusGuard {
    private static thresholds: Record<string, { amount: number; transactions: number }> = {
        "NY": { amount: 500000, transactions: 100 },
        "CA": { amount: 500000, transactions: 0 },
        "TX": { amount: 500000, transactions: 0 },
        "FL": { amount: 100000, transactions: 0 }
    };

    static checkNexus(state: string, ytdSales: number, transactions: number = 0, claimedCollectsTax?: unknown): { verified: boolean; error?: string } {
        if (typeof state !== 'string') {
            return {
                verified: false,
                error: "state must be a string."
            };
        }
        const stateCode = state.toUpperCase();
        const t = this.thresholds[stateCode];
        if (!t) {
            return {
                verified: false,
                error: `State ${stateCode} not in configured nexus threshold table. Cannot verify nexus liability — block pending rule configuration.`
            };
        }

        // NaN >= threshold is false, so non-finite sales would silently read
        // as below-threshold. Fail closed, matching the Python guard.
        if (typeof ytdSales !== 'number' || !Number.isFinite(ytdSales)) {
            return {
                verified: false,
                error: "ytd_sales must be a finite numeric value."
            };
        }
        if (typeof transactions !== 'number' || !Number.isFinite(transactions)) {
            return {
                verified: false,
                error: "transactions must be a finite numeric value."
            };
        }
        // Negative sales are malformed facts, not "below threshold" — reject
        // them explicitly, matching the other guards' non-negative pattern.
        if (ytdSales < 0) {
            return {
                verified: false,
                error: "ytd_sales must be a non-negative numeric value."
            };
        }
        if (transactions < 0) {
            return {
                verified: false,
                error: "transactions must be a non-negative numeric value."
            };
        }

        const hit = ytdSales >= t.amount || (t.transactions > 0 && transactions >= t.transactions);
        if (typeof claimedCollectsTax !== 'boolean') {
            return {
                verified: false,
                error: "Computed nexus liability only. Provide claimed_collects_tax as a boolean for deterministic verification."
            };
        }

        if (claimedCollectsTax !== hit) {
            return {
                verified: false,
                error: hit
                    ? `Nexus threshold exceeded in ${state}. Registration required.`
                    : `Nexus claim mismatch: ${state} is below its configured threshold, but tax collection was claimed.`
            };
        }
        return { verified: true };
    }
}

export class TaxPreFlight {
    static audit(intent: any): { allowed: boolean, blocks: string[] } {
        const blocks: string[] = [];

        // 1. Classification
        if (intent.worker_facts) {
            const status = ClassificationGuard.verifyWorkerStatus(
                intent.worker_facts.provides_tools,
                intent.worker_facts.reimburses_expenses,
                intent.worker_facts.indefinite_relationship
            );
            if (intent.worker_type && intent.worker_type !== status) {
                blocks.push(`Misclassification Risk: Logic says ${status}, Intent says ${intent.worker_type}`);
            }
        }

        // 2. Nexus — run whenever sales data is provided; falsy, undefined,
        // or non-object values must fail closed, not skip validation
        // (Greptile review on #65). Presence is hasOwnProperty-only — the
        // same semantics the structured claim below uses, so an explicit
        // `sales_data: undefined` is malformed input, not an absent field.
        const hasSalesData = Object.prototype.hasOwnProperty.call(intent, 'sales_data');
        if (hasSalesData) {
            const salesData = intent.sales_data;
            if (typeof salesData !== 'object' || salesData === null || Array.isArray(salesData)) {
                blocks.push('sales_data must be an object with numeric amount and transactions fields.');
            } else {
                const hasStructuredClaim = Object.prototype.hasOwnProperty.call(intent, 'claimed_collects_tax');
                const claimedCollectsTax = hasStructuredClaim
                    ? intent.claimed_collects_tax
                    : intent.tax_decision === 'no_tax' ? false : undefined;
                const check = NexusGuard.checkNexus(
                    intent.state,
                    salesData.amount,
                    salesData.transactions,
                    claimedCollectsTax
                );
                if (!check.verified) {
                    blocks.push(check.error!);
                }
            }
        }

        return { allowed: blocks.length === 0, blocks };
    }
}
