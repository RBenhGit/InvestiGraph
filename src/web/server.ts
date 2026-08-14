import { fileURLToPath } from 'node:url';
import path from 'node:path';
import Fastify from 'fastify';
import fastifyStatic from '@fastify/static';
import { fetchStockData } from '../data/twelvedata';
import { calculateLynchValue } from '../valuation/lynch';
import { calculateRuleOneValue } from '../valuation/ruleOne';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT) || 3000;

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
  fastify.listen({ port: PORT }, (err, address) => {
    if (err) {
      fastify.log.error(err);
      process.exit(1);
    }
    console.log(`Listening on ${address}`);
  });
}
