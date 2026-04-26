import api from './client'

export interface CountyCreatePayload {
  name: string
  state: string
  portal_url: string
  scraper_adapter: string
  appeal_deadline_days: number
  approval_rate_hist: number | null
}

export async function createCounty(data: CountyCreatePayload): Promise<void> {
  await api.post('/counties', data)
}

export async function triggerScrape(countyId: string): Promise<void> {
  await api.post(`/counties/${countyId}/scrape`)
}


export async function triggerScoring(countyId?: string): Promise<void> {
  await api.post('/scoring/run', null, {
    params: countyId ? { county_id: countyId } : {},
  })
}
