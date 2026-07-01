import { NextResponse } from 'next/server';
import pdfMap from '@/lib/pdf_page_mapping.json';

export async function GET() {
  return NextResponse.json(pdfMap);
}
