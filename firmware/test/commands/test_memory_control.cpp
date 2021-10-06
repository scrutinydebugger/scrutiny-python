#include <gtest/gtest.h>
#include "scrutiny.h"
#include "scrutiny_test.h"

class TestMemoryControl : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;
   scrutiny::config config

   TestMemoryControl() {}

   virtual void SetUp() 
   {
      scrutiny::Config config;
      scrutiny_handler.init(&config);
      scrutiny_handler.force_comm_connect();
   }
};

TEST_F(TestMemoryControl, TestReadSingleAddress) 
{

}

