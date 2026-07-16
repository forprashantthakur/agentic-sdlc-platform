import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import Stepper, { STEPS } from '../components/Stepper'
import BusinessContext from './steps/BusinessContext'
import KnowledgeIngestion from './steps/KnowledgeIngestion'
import Discovery from './steps/Discovery'
import AiAnalysis from './steps/AiAnalysis'
import Review from './steps/Review'
import GenerateBrd from './steps/GenerateBrd'

export default function NewBrd({ project, setProject, run, setRun }) {
  // The email-intake flow starts a run and jumps straight to the live agent view. It passes the
  // desired step (and the steps already behind us) through router state so the stepper reads right.
  const location = useLocation()
  const startStep = location.state?.step || 'context'
  const [step, setStep] = useState(startStep)
  const [done, setDone] = useState(location.state?.completed || [])

  const advance = (from) => {
    setDone((d) => (d.includes(from) ? d : [...d, from]))
    const i = STEPS.findIndex((s) => s.id === from)
    setStep(STEPS[i + 1]?.id ?? from)
  }
  const back = (from) => {
    const i = STEPS.findIndex((s) => s.id === from)
    setStep(STEPS[i - 1]?.id ?? from)
  }

  return (
    <>
      <Stepper current={step} completed={done} onSelect={setStep} />
      {step === 'context' && <BusinessContext project={project} onCreated={setProject} onNext={() => advance('context')} />}
      {step === 'ingestion' && <KnowledgeIngestion project={project} onNext={() => advance('ingestion')} onBack={() => back('ingestion')} />}
      {step === 'discovery' && <Discovery project={project} onNext={() => advance('discovery')} onBack={() => back('discovery')} />}
      {step === 'analysis' && <AiAnalysis project={project} run={run} setRun={setRun} onNext={() => advance('analysis')} onBack={() => back('analysis')} />}
      {step === 'review' && (
        <Review project={project} onNext={() => advance('review')} onBack={() => back('review')}
          onWatchRun={() => setStep('analysis')} />
      )}
      {step === 'generate' && <GenerateBrd project={project} onBack={() => back('generate')} />}
    </>
  )
}
