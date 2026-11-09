import SwaggerUI from 'swagger-ui-react'
import 'swagger-ui-react/swagger-ui.css'

// Le fichier est copié dans public/ pour être servi à /openapi.yaml
export default function ApiDocs() {
  return (
    <div className="swagger-wrap" style={{ maxWidth: 1100, margin: '0 auto' }}>
      <SwaggerUI url="/openapi.yaml" docExpansion="list" />
    </div>
  )
}
