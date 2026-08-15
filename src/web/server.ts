import { fileURLToPath } from 'node:url';
import path from 'node:path';
import Fastify from 'fastify';
import fastifyStatic from '@fastify/static';
import { fetchStockData } from '../data/twelvedata';
import { calculateLynchValue } from '../valuation/lynch';
import { calculateRuleOneValue } from '../valuation/ruleOne';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// 3000/3001/3100 are already claimed by other projects on this machine (stock_vision, etc.) —
// default to a port that doesn't collide.
const PORT = Number(process.env.PORT) || 3210;

interface ValuateRequestBody {
  ticker: string;
  growthRatePercent: number;
  exitPeMultiple: number;
  requiredReturnPercent: number;
  years: number;
}

export function buildServer() {
  const fastify = Fastify();

  fastify.register(fastifyStatic, {
    root: path.join(__dirname, 'public'),
  });

  fastify.post<{ Body: ValuateRequestBody }>('/api/valuate', async (request, reply) => {
    const { ticker, growthRatePercent, exitPeMultiple, requiredReturnPercent, years } =
      request.body;

    const result = await fetchStockData(ticker);

    if (!result.ok) {
      const status = result.error.type === 'NOT_FOUND' ? 404 : 400;
      return reply.status(status).send({ ok: false, error: result.error });
    }

    const { data } = result;
    const lynch = calculateLynchValue(data.epsTtm, growthRatePercent);
    const ruleOne = calculateRuleOneValue(
      data.epsTtm,
      growthRatePercent,
      exitPeMultiple,
      requiredReturnPercent,
      years,
    );

    return reply.status(200).send({ ok: true, data, lynch, ruleOne });
  });

  return fastify;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const fastify = buildServer();
  // Bind to all interfaces (not just loopback) so the dev tool is reachable over Tailscale/LAN,
  // not only from this machine.
  fastify.listen({ port: PORT, host: '0.0.0.0' }, (err, address) => {
    if (err) {
      fastify.log.error(err);
      process.exit(1);
    }
    console.log(`Listening on ${address}`);
  });
}
