package com.continuumio.rambling

import java.util.Collections

import org.apache.hadoop.fs.Path
import org.apache.hadoop.yarn.api.ApplicationConstants
import org.apache.hadoop.yarn.api.records._
import org.apache.hadoop.yarn.client.api.AMRMClient.ContainerRequest
import org.apache.hadoop.yarn.client.api.{AMRMClient, NMClient}
import org.apache.hadoop.yarn.conf.YarnConfiguration
import org.apache.hadoop.yarn.util.Records
import Utils._

import scala.collection.JavaConverters._


object ApplicationMaster {


  def main(args: Array[String]) {
    val jarPath = args(0)
    val n = args(1).toInt
    val shellCMD = args.drop(2)
    println(shellCMD.mkString(" "))
    println("BEEP!")
    val test = "\""+shellCMD.mkString(" ")+"\""

    implicit val conf = new YarnConfiguration()

    // Create a client to talk to the RM
    val rmClient = AMRMClient.createAMRMClient().asInstanceOf[AMRMClient[ContainerRequest]]
    rmClient.init(conf)
    rmClient.start()
    rmClient.registerApplicationMaster("", 0, "")


    //create a client to talk to NM
    val nmClient = NMClient.createNMClient()
    nmClient.init(conf)
    nmClient.start()

    val priority = Records.newRecord(classOf[Priority])
    priority.setPriority(0)

    //resources needed by each container
    val resource = Records.newRecord(classOf[Resource])
    resource.setMemory(128)
    resource.setVirtualCores(1)


    //request for containers
    for ( i <- 1 to n) {
      val containerAsk = new ContainerRequest(resource,null,null,priority)
      println("asking for " +s"$i")
      rmClient.addContainerRequest(containerAsk)
    }

    var responseId = 0
    var completedContainers = 0

    while( completedContainers < n) {

      val appMasterJar = Records.newRecord(classOf[LocalResource])
      setUpLocalResource(new Path(jarPath),appMasterJar)

      val env = collection.mutable.Map[String,String]()
      setUpEnv(env)

      val response = rmClient.allocate(responseId+1)
      responseId+=1
      for (container <- response.getAllocatedContainers.asScala) {
        val ctx =
          Records.newRecord(classOf[ContainerLaunchContext])
        ctx.setCommands(
          List(
            "python -c 'import sys; print(sys.path); import random; print(str(random.random()))'" +
              " 1>" + ApplicationConstants.LOG_DIR_EXPANSION_VAR + "/stdout" +
              " 2>" + ApplicationConstants.LOG_DIR_EXPANSION_VAR + "/stderr"
          ).asJava
        )
        ctx.setEnvironment(env.asJava)

        System.out.println("Launching container " + container)
        nmClient.startContainer(container, ctx)
      }

      for ( status <- response.getCompletedContainersStatuses.asScala){
        println("completed"+status.getContainerId)
        completedContainers+=1

      }

      Thread.sleep(10000)
    }

    rmClient.unregisterApplicationMaster(
      FinalApplicationStatus.SUCCEEDED, "", "")
  }

}