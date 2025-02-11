/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // Skip OG route generation during static export
  experimental: {
    skipTrailingSlashRedirect: true,
  },
  distDir: 'out'
}

module.exports = nextConfig 