/**
 * Welcome to Cloudflare Workers!
 *
 * This worker implements IP-based rate-limiting using Cloudflare KV.
 *
 * - It intercepts all incoming requests.
 * - It identifies the client's IP address.
 * - It uses a KV namespace to track the number of requests from that IP
 *   within a specific time window (60 seconds).
 * - If an IP exceeds the defined request limit, it blocks the request
 *   with a 429 "Too Many Requests" error.
 * - Otherwise, it forwards the request to the origin server.
 *
 * Bind resources to your worker in `wrangler.jsonc`. After adding bindings, a type definition for the
 * `Env` object can be regenerated with `npm run cf-typegen`.
 */

// Define the structure of the environment object, including the KV namespace binding.
// The `cf-typegen` command will automatically update this based on `wrangler.jsonc`.
interface Env {
	RATE_LIMITER_KV: KVNamespace;
}

const RATE_LIMIT_WINDOW_SECONDS = 60;
const MAX_REQUESTS_PER_WINDOW = 20;

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
		// Get the client's IP address from the "CF-Connecting-IP" header.
		const ip = request.headers.get('CF-Connecting-IP');

		// If the IP address is not available, block the request.
		if (!ip) {
			return new Response('Could not determine client IP.', { status: 400 });
		}

		const currentTime = Math.floor(Date.now() / 1000);
		const currentWindowStart = Math.floor(currentTime / RATE_LIMIT_WINDOW_SECONDS);
		const key = `${ip}:${currentWindowStart}`;

		// Get the current request count for this IP in the current time window.
		const { value, metadata } = await env.RATE_LIMITER_KV.getWithMetadata<{ count: number }>(key);

		let requestCount = value ? parseInt(value, 10) : 0;
		requestCount++;

		// If the request count exceeds the limit, block the request.
		if (requestCount > MAX_REQUESTS_PER_WINDOW) {
			return new Response('Too Many Requests', { status: 429 });
		}

		// Store the new request count in KV.
		// The entry will automatically expire at the end of the time window.
		await env.RATE_LIMITER_KV.put(key, requestCount.toString(), {
			expirationTtl: RATE_LIMIT_WINDOW_SECONDS,
		});

		// If the request is within the limit, forward it to the origin.
		// This assumes you have a configured origin. If the worker is standalone,
		// you would return a direct response here.
		return fetch(request);
	},
} satisfies ExportedHandler<Env>;